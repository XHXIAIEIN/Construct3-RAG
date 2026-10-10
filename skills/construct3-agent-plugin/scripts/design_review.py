"""Prepare complete design questions and validate answers against live inputs."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import c3project as c3
import print_sheet

FORMAT = 1
VERDICTS = {"pass", "needs_change", "insufficient_evidence"}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def save(path: Path, value: object) -> None:
    """Replace one complete artifact; interrupted runs keep the previous one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    draft = path.with_suffix(path.suffix + ".tmp")
    draft.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(draft, path)


def rules(p: c3.Project) -> dict:
    scripts = Path(__file__).parent
    paths = [scripts / name for name in ("review_design.py", "design_review.py", "print_sheet.py", "c3project.py")]
    paths += [p.rag / "prompts" / name for name in ("event-sheet-thinking.md", "event-sheet-style.md")]
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"
            for path in paths}


def own(row) -> dict:
    return {k: v for k, v in row.ev.items() if k != "children"}


def context(d, seeds: list, broad: bool) -> tuple[list, list[str]]:
    """Follow shared state and calls; dynamic calls widen to every sheet."""
    rows = list(d.all_rows())
    symbols = {str(e.ev.get("name", "")).lower() for e in rows if e.kind == "variable" and e.depth == 0}
    symbols |= {str(e.ev.get("functionName", "")).lower() for e in rows if e.kind == "function-block"}
    symbols |= {str(e.ev.get("aceName", "")).lower() for e in rows if e.kind == "custom-ace-block"}
    symbols.discard("")
    tokens = {e: {s.lower() for s in re.findall(r"\b[A-Za-z_]\w*\b", json.dumps(own(e)))} & symbols
              for e in rows}
    selected = set(rows if broad else seeds)
    for e in seeds:
        selected.update(r for r in rows if r.parent is e.parent and r.sheet == e.sheet
                        and (e.parent is not None or abs(r.n - e.n) <= 1))
    missing = []
    functions = {str(e.ev.get("functionName", "")) for e in rows if e.kind == "function-block"}
    while True:
        before = set(selected)
        for e in list(selected):
            selected.update(e.ancestors())
            selected.update(e.subtree())
            if e.kind in {"script", "include", "custom-ace-block"}:
                selected.update(rows)
            if e.kind == "include" and e.ev.get("includeSheet") not in d.sheets:
                missing.append(f"Included sheet {e.ev.get('includeSheet')!r} is missing")
            for ace in [*e.conditions, *e.actions]:
                called = ace.get("callFunction")
                if called and called not in functions:
                    missing.append(f"Function {called!r} has no definition in the listed sheets")
                if "mapped" in str(ace.get("id", "")):
                    selected.update(rows)
                    missing.append("Mapped function target is unresolved; verify the dispatch at runtime")
        used = set().union(*(tokens[e] for e in selected)) if selected else set()
        selected.update(e for e in rows if tokens[e] & used)
        if before == selected:
            break
    return [e for e in rows if e in selected], sorted(set(missing))


def packets(p: c3.Project, d, found: list[dict], sheets: list[str], questions: dict) -> dict:
    """Keep deterministic findings separate from the questions a reader judges."""
    candidates = [f for f in found if f["sheet"] in sheets]
    specs = [f for f in candidates if f["ask"]]
    for sheet in sheets:
        for ask in questions:
            if not any(f["sheet"] == sheet and f["ask"] == ask for f in specs):
                specs.append({"sheet": sheet, "ask": ask, "rule": "coverage", "variant": "",
                              "events": [], "event": None, "short": "No candidate located"})
    printed = {name: {id(r.event): r for r in print_sheet.sheet_rows(p, s.get("events", []), [0])}
               for name, s in d.sheets.items()}
    version = rules(p)
    out = []
    for spec in specs:
        sheet = spec["sheet"]
        seeds = [e for e in d.rows[sheet] if e.n in spec["events"] and e.kind in c3.NUMBERED]
        if not seeds:
            seeds = list(d.rows[sheet])
        broad = not spec["events"]
        selected, missing = context(d, seeds, broad)
        missing += list(p.findings.errors)
        evidence = []
        relations = []
        dependencies = {"project.c3proj": digest(p.data)}

        def add(source: str, text: str, value: object) -> None:
            key = "E" + digest(source)[:16]
            if not any(e["id"] == key for e in evidence):
                evidence.append({"id": key, "source": source, "text": text})
                dependencies[source] = digest(value)

        targets = []
        used_objects = set()

        def relate(kind: str, caller: object, target: object, source: str) -> None:
            relations.append({"kind": kind, "from": caller, "to": target,
                              "evidence": "E" + digest(source)[:16], "origin": "project_format"})

        for e in selected:
            sid = e.ev.get("sid")
            row = printed[e.sheet][id(e.ev)]
            source = f"eventSheets/{e.sheet}:sid={sid}"
            add(source, "\n".join([*row.head, *row.body]), own(e))
            targets.append({"sheet": e.sheet, "sid": sid, "event": e.n})
            caller = {"sheet": e.sheet, "sid": sid}
            if e.kind == "include":
                relate("includes_sheet", caller, e.ev.get("includeSheet"), source)
            text = json.dumps(own(e))
            used_objects.update(name for name in p.plugin_of if re.search(rf"\b{re.escape(name)}\b", text))
            for kind, aces in (("conditions", e.conditions), ("actions", e.actions)):
                for ace in aces:
                    if ace.get("callFunction"):
                        relate("calls_function", caller, ace["callFunction"], source)
                        continue
                    if "customAction" in ace:
                        owner = ace.get("customActionObjectClass", ace.get("objectClass"))
                        blocks = [r for r in selected if r.kind == "custom-ace-block"
                                  and r.ev.get("aceName") == ace["customAction"]
                                  and r.ev.get("objectClass") in [owner, *p.families_of(owner)]]
                        relate("calls_custom_action", caller, {"object": owner, "action": ace["customAction"]}, source)
                        if not blocks:
                            missing.append(f"Custom action {owner}.{ace['customAction']} is missing")
                        continue
                    if ace.get("type") in {"comment", "script"}:
                        if ace["type"] == "script":
                            missing.append("Action script effects are unresolved; verify them in the preview")
                        continue
                    if ace.get("id") == "comment":
                        continue
                    obj = ace.get("objectClass")
                    if obj in p.types or obj in p.families:
                        relate("uses_object", caller, obj, source)
                    params = ace.get("parameters") or {}
                    if isinstance(params, dict) and ace.get("id") in {"set-eventvar-value", "add-to-eventvar",
                            "subtract-from-eventvar", "set-boolean-eventvar", "toggle-boolean-eventvar"}:
                        relate("writes_variable", caller, params.get("variable"), source)
                    for expression in d.expressions(kind, ace).values():
                        for name in d.globals():
                            if re.search(rf"\b{re.escape(name)}\b", rd_blank(expression), re.I):
                                relate("reads_variable", caller, name, source)
                    entry = p.ace_entry(kind, ace) if ace.get("objectClass") in p.plugin_of else None
                    ace_source = f"schema/{ace.get('objectClass')}/{ace.get('behaviorType', '')}/{kind}/{ace.get('id')}"
                    if entry is None:
                        missing.append(f"No schema evidence for {ace_source}")
                    else:
                        add(ace_source, json.dumps(entry, ensure_ascii=False, sort_keys=True), entry)
        for name in sorted(used_objects):
            if name in p.types:
                add(f"objectTypes/{name}", json.dumps(p.types[name], ensure_ascii=False), p.types[name])
            for family in p.families_of(name) + ([name] if name in p.families else []):
                add(f"families/{family}", json.dumps(p.families[family], ensure_ascii=False), p.families[family])
                for member in p.families[family].get("members", []):
                    relate("contains_member", family, member, f"families/{family}")
                    if member in p.types:
                        add(f"objectTypes/{member}", json.dumps(p.types[member], ensure_ascii=False), p.types[member])
        # Layouts establish picking, initial values and hierarchy links.
        for name, layout in d.layouts.items():
            if broad or layout.get("eventSheet") in {e.sheet for e in selected}:
                add(f"layouts/{name}", json.dumps(layout, ensure_ascii=False), layout)
                relate("runs_sheet", name, layout.get("eventSheet"), f"layouts/{name}")
        for path in p.script_files():
            add(path.as_posix(), (p.root / path).read_text(encoding="utf-8"), (p.root / path).read_text(encoding="utf-8"))
            missing.append("Script imports and runtime effects are unresolved; verify them in the preview")
        guide = p.rag / "prompts" / "event-sheet-thinking.md"
        if guide.exists():
            text = guide.read_text(encoding="utf-8")
            model = text.split("## The model\n", 1)[-1].split("## Rules\n", 1)[0]
            add("prompts/event-sheet-thinking.md#the-model", model, text)
        else:
            missing.append("Design constraints are missing; supply prompts/event-sheet-thinking.md")
        identity = {"sheet": sheet, "question": spec["ask"], "rule": spec["rule"], "variant": spec["variant"],
                    "sids": [e.ev.get("sid") for e in seeds] if not broad else [],
                    "subject": spec["short"] if broad and spec["rule"] != "coverage" else ""}
        issue_id = "Q" + digest(identity)[:20]
        item = {"id": issue_id, "location": identity, "question": questions[spec["ask"]],
                "criterion": "Judge whether the proposed simplification preserves picking, order and visible behavior. "
                             "Return insufficient_evidence when intent or runtime behavior is needed.",
                "verdicts": sorted(VERDICTS), "evidence": evidence, "targets": targets,
                "relations": list({digest(r): r for r in relations}.values()),
                "impact": "Selected events and shared definitions; lexical dependency closure may include extra "
                          "events. Unresolved links widen scope. Absence of a relation does not prove no impact.",
                "preserve": "Existing player inputs, selected instances, state transitions and timing",
                "missing": sorted(set(missing)), "dependencies": dependencies,
                "rules": version, "schema_version": p.index.get("version"), "locale": p.locale}
        # Event numbers locate an edit, but do not invalidate an unchanged judgement.
        item["input_version"] = digest({k: item[k] for k in
                                        ("dependencies", "rules", "schema_version", "locale", "question", "missing")})
        out.append(item)
    return {"format": FORMAT, "project": digest(str(p.root.resolve())), "sheets": sheets,
            "findings": [f for f in candidates if f["ask"] is None], "questions": out,
            "runtime": "pending: run the full checker, open the editor and drive the target input"}


def rd_blank(expression: str) -> str:
    return c3.STRING_LITERAL.sub(" ", expression)


def batch_document(items: list[dict]) -> dict:
    """Share identical evidence within one complete batch."""
    evidence = {e["id"]: e for q in items for e in q["evidence"]}
    return {"format": FORMAT, "evidence": list(evidence.values()),
            "questions": [{**q, "evidence": [e["id"] for e in q["evidence"]]} for q in items]}


def validate(items: list[dict], answers: object, complete: bool = True) -> list[dict]:
    """Validate identity, citations and scope; the judgement remains the reader's."""
    if not isinstance(answers, list):
        raise ValueError("answers must be a JSON list; read answer-format.json")
    expected = {item["id"]: item for item in items}
    seen = set()
    for answer in answers:
        if not isinstance(answer, dict) or set(answer) != {"id", "input_version", "verdict", "evidence", "reason", "suggestions"}:
            raise ValueError("each answer needs exactly id, input_version, verdict, evidence, reason and suggestions")
        key = answer["id"]
        if not isinstance(key, str) or key not in expected or key in seen:
            raise ValueError(f"unknown or duplicate question {key!r}; prepare the current batch")
        seen.add(key)
        item = expected[key]
        if answer["input_version"] != item["input_version"]:
            raise ValueError(f"stale input for {key}; prepare again and answer its current evidence")
        verdict = answer["verdict"]
        if not isinstance(verdict, str) or verdict not in VERDICTS:
            raise ValueError(f"invalid verdict for {key}; use {sorted(VERDICTS)}")
        if not isinstance(answer["reason"], str) or not answer["reason"].strip():
            raise ValueError(f"{key} needs a reason")
        if item["missing"] and verdict != "insufficient_evidence":
            raise ValueError(f"{key} lacks dependencies; return insufficient_evidence")
        cited = answer["evidence"]
        facts = {e["id"]: e["text"] for e in item["evidence"]}
        if not isinstance(cited, list) or not cited:
            raise ValueError(f"{key} needs evidence citations")
        for citation in cited:
            if not isinstance(citation, dict) or set(citation) != {"id", "quote"}:
                raise ValueError(f"{key}: each citation needs id and quote")
            if not isinstance(citation["id"], str) or citation["id"] not in facts \
                    or not isinstance(citation["quote"], str) or not citation["quote"].strip() \
                    or citation["quote"] not in facts[citation["id"]]:
                raise ValueError(f"{key}: evidence id or quote is not in this packet")
        suggestions = answer["suggestions"]
        allowed = {(t["sheet"], t["sid"]) for t in item["targets"]}
        if not isinstance(suggestions, list) or (verdict == "needs_change" and not suggestions):
            raise ValueError(f"{key}: needs_change needs a scoped suggestion")
        for suggestion in suggestions:
            if not isinstance(suggestion, dict) or set(suggestion) != {"sheet", "sid", "text"} \
                    or not isinstance(suggestion["sheet"], str) or not isinstance(suggestion["sid"], int) \
                    or (suggestion["sheet"], suggestion["sid"]) not in allowed \
                    or not isinstance(suggestion["text"], str) or not suggestion["text"].strip():
                raise ValueError(f"{key}: suggestion is outside its event scope; prepare the affected sheets")
    if complete and seen != set(expected):
        raise ValueError(f"missing {len(set(expected) - seen)} answer(s); answer every question in the batch")
    return answers


def run(p, d, found, sheets, questions, args) -> int:
    folder = Path(args.prepare)
    folder = (p.root / folder).resolve() if not folder.is_absolute() else folder.resolve()
    if not folder.is_relative_to(p.root.resolve()) or folder == p.root.resolve():
        raise ValueError("--prepare must name an output folder inside the game, such as .tmp/design-review")
    if args.check:
        command = [sys.executable, str(Path(__file__).with_name("check_project.py")), "--project", str(p.root),
                   "--rag", str(p.rag), "--locale", p.locale, "--limit", "0"]
        if args.style:
            command.append("--style")
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=120)
        except subprocess.TimeoutExpired as error:
            save(folder / "check.json", {"command": command, "status": "timeout", "seconds": error.timeout})
            raise ValueError("checker timed out; read check.json and rerun check_project.py") from error
        save(folder / "check.json", {"command": command, "exit": result.returncode,
                                   "stdout": result.stdout, "stderr": result.stderr})
        lines = (result.stdout + result.stderr).splitlines()
        count = c3.fitting(lines, args.limit) if args.limit else len(lines)
        print("\n".join(lines[:count]))
        print(f"check: exit {result.returncode}; complete log {folder / 'check.json'}")
        if result.returncode:
            print("stopped before design questions: fix checker findings, then repeat --check --prepare")
            return result.returncode
    # Re-read after the checker, and refuse a save during preparation.
    import review_design as review
    before = source_snapshot(p.root)
    p = c3.Project(p.root, p.rag, p.locale, c3.Findings())
    d = review.Design.of(p)
    found = review.review(d)
    bundle = packets(p, d, found, sheets, questions)
    accepted = []
    invalidated = []
    if args.resume and (folder / "accepted.json").exists():
        cache = c3.load(folder / "accepted.json")
        if not isinstance(cache, dict) or cache.get("project") != bundle["project"] or cache.get("format") != FORMAT \
                or not isinstance(cache.get("answers"), list):
            raise ValueError("accepted.json belongs to another project; use another --prepare folder")
        seen = set()
        for answer in cache.get("answers", []):
            try:
                validate(bundle["questions"], [answer], complete=False)
                if answer["id"] in seen:
                    raise ValueError("duplicate cached answer")
                seen.add(answer["id"])
            except ValueError as error:
                invalidated.append(str(error))
                continue
            if answer["verdict"] != "insufficient_evidence":
                accepted.append(answer)
    reused = {a["id"] for a in accepted}
    pending = [q for q in bundle["questions"] if q["id"] not in reused]
    batches, batch, size = [], [], 0
    for item in pending:
        size = len(json.dumps(batch_document([*batch, item]), ensure_ascii=False))
        if batch and args.limit and size > args.limit:
            batches.append(batch)
            batch, size = [], 0
        batch.append(item)
    if batch:
        batches.append(batch)
    if args.batch is not None and not 1 <= args.batch <= len(batches):
        raise ValueError(f"--batch is 1 through {len(batches)}; prepare without --batch to see pending work")
    selected = batches[args.batch - 1] if args.batch is not None else pending
    if args.answers:
        answers = validate(selected, c3.load(Path(args.answers)))
        accepted += answers
    if before != source_snapshot(p.root):
        raise ValueError("project inputs changed during preparation; rerun after the editor has saved and closed")
    if args.answers:
        save(folder / "accepted.json", {"format": FORMAT, "project": bundle["project"], "answers": accepted})
    bundle["reused"] = sorted(reused)
    bundle["invalidated"] = invalidated
    bundle["accepted"] = accepted
    generation = digest(bundle)[:20]
    for n, batch in enumerate(batches, 1):
        save(folder / generation / f"batch-{n}.json", batch_document(batch))
    bundle["batches"] = [f"{generation}/batch-{n}.json" for n in range(1, len(batches) + 1)]
    manifest = {**bundle, "questions": [{k: q[k] for k in ("id", "location", "input_version", "missing")}
                                        for q in bundle["questions"]]}
    save(folder / "current.json", manifest)
    save(folder / "answer-format.json", [{"id": "copy the question id", "input_version": "copy its input_version",
          "verdict": "pass | needs_change | insufficient_evidence", "evidence": [{"id": "copy an evidence id",
          "quote": "copy a short exact excerpt"}], "reason": "why the evidence supports the verdict",
          "suggestions": [{"sheet": "copy a target sheet", "sid": 123, "text": "describe the scoped change"}]}])
    print(f"design: {len(bundle['findings'])} deterministic findings; {len(pending)} questions; {len(reused)} reused")
    print(f"prepared: {folder / 'current.json'}; {len(batches)} complete batches (large questions stay whole)")
    lines = [f"batch {n}: {folder / name}" for n, name in enumerate(bundle["batches"], 1)]
    shown = c3.fitting(lines, max(1, args.limit - 900)) if args.limit else len(lines)
    print("\n".join(lines[:shown]))
    if shown < len(lines):
        print(f"{len(lines) - shown} batches remain; current.json lists every batch")
    if invalidated:
        print(f"{len(invalidated)} cached answers invalidated; current.json keeps the reasons")
    print("next: read current.json findings and each batch; write answers using answer-format.json; "
          "run --prepare with --answers FILE, optionally --batch N and --resume. Answers only save judgements; "
          "edit through edit_sheet.py with event numbers and copied printed lines. "
          "Validation checks structure, not semantic correctness. " + bundle["runtime"])
    return 0


def source_snapshot(root: Path) -> dict:
    paths = [root / "project.c3proj"]
    for name in ("eventSheets", "layouts", "objectTypes", "families", "scripts"):
        paths.extend(p for p in (root / name).rglob("*") if p.is_file() and not p.name.endswith(".uistate.json"))
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
