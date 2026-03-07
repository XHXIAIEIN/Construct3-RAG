#!/usr/bin/env python3
"""
Construct 3 RAG Benchmark
基于预定义问答题集评估 RAG 系统的回答质量。

使用方式:
    python scripts/benchmark.py
    python scripts/benchmark.py --mode smart      # 使用 answer_smart (默认)
    python scripts/benchmark.py --mode stream     # 使用 answer_stream
    python scripts/benchmark.py --mode high       # 使用 answer_high_confidence
    python scripts/benchmark.py --output report.md
"""

from src.config import QDRANT_HOST, QDRANT_PORT, LLM_MODEL, LLM_BASE_URL, LLM_PROVIDER, LLM_API_KEY
from src.rag.chain import RAGChain, RAGResponse
import sys
import time
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Benchmark 题集
# =============================================================================

@dataclass
class BenchmarkCase:
    """单个评估用例"""
    id: str
    question: str
    expected_keywords: List[str]   # 答案中应包含的关键词
    forbidden_phrases: List[str] = field(default_factory=list)  # 不应出现的词（幻觉词）
    category: str = "general"      # 分类标签
    note: str = ""                 # 备注

    # 是否预期有明确答案（False 表示文档可能确实没有）
    has_answer: bool = True


BENCHMARK_CASES: List[BenchmarkCase] = [
    # --- 基础概念 ---
    BenchmarkCase(
        id="B01",
        category="概念",
        question="Sprite 对象是什么？它的主要用途是什么？",
        expected_keywords=["Sprite", "图像", "动画", "精灵", "碰撞"],
        note="基础插件概念"
    ),
    BenchmarkCase(
        id="B02",
        category="概念",
        question="事件表（Event Sheet）是什么？",
        expected_keywords=["事件", "条件", "动作", "表达式"],
        note="核心概念"
    ),
    BenchmarkCase(
        id="B03",
        category="概念",
        question="实例变量和全局变量的区别是什么？",
        expected_keywords=["实例", "全局", "静态", "作用域"],
        note="变量作用域"
    ),

    # --- 插件用法 ---
    BenchmarkCase(
        id="B04",
        category="插件",
        question="平台(Platform) 行为有哪些主要参数？",
        expected_keywords=["平台", "最大移动速度", "加速度", "减速度", "重力",
                           "跳跃高度", "最大下落速度", "跳跃维持", "二段跳"],
        note="Platform 行为配置"
    ),
    BenchmarkCase(
        id="B05",
        category="插件",
        question="补间(Tween) 行为怎么用？如何让对象移动到指定位置？",
        expected_keywords=["补间", "两个参数", "位置", "过渡",  "时间", "曲线"],
        note="Tween 行为用法"
    ),
    BenchmarkCase(
        id="B06",
        category="插件",
        question="键盘(Keyboard) 插件如何检测按键？按住(on key pressed) 和按下(is key down) 的区别？",
        expected_keywords=["键盘", "按键", "按键码", "按住", "按下", "持续", "单次"],
        note="输入检测差异"
    ),

    # --- 系统功能 ---
    BenchmarkCase(
        id="B07",
        category="系统",
        question="系统(System) 对象的遍历(For each) 条件如何使用？",
        expected_keywords=["条件", "循环", "遍历",
                           "对象", "实例", "范围", "跳出", "loopindex"],
        note="循环遍历对象"
    ),
    BenchmarkCase(
        id="B08",
        category="系统",
        question="如何在 Construct 3 中实现计时器？",
        expected_keywords=["计时", "正在计时", "计时结束", "遍历"],
        note="计时器实现方式"
    ),
    BenchmarkCase(
        id="B09",
        category="系统",
        question="等待信号(Wait for signal) 和 等待X秒(Wait X seconds) 有什么区别？",
        expected_keywords=["信号", "异步", "秒", "时间", "等待"],
        note="等待机制"
    ),

    # --- 工作流 ---
    BenchmarkCase(
        id="B10",
        category="工作流",
        question="如何让玩家按空格键跳跃？并且播放跳跃动画？",
        expected_keywords=["键盘", "空格", "模拟控制",
                           "跳跃", "平台", "条件", "正在跳跃", "准备起跳", "动画"],
        note="经典平台游戏跳跃"
    ),
    BenchmarkCase(
        id="B11",
        category="工作流",
        question="如何实现碰撞检测？Sprite 和 Sprite 碰撞时触发事件",
        expected_keywords=["碰撞", "重叠", "家族"],
        note="碰撞事件"
    ),
    BenchmarkCase(
        id="B12",
        category="工作流",
        question="如何用事件表实现分数系统？包括变量定义和 UI 更新",
        expected_keywords=["变量", "分数", "设置文本", "动作组"],
        note="分数系统工作流"
    ),

    # --- 脚本 API ---
    BenchmarkCase(
        id="B13",
        category="脚本",
        question="在 Construct 3 脚本中如何获取一个对象的实例？",
        expected_keywords=["runtime", "objects", "getInstance",
                           "getInstanceByUid", "getFirstInstance", "getAllInstances", "getPickedInstances", "getPairedInstance"],
        note="脚本 API 基础。相关文档：https://www.construct.net/en/make-games/manuals/construct-3/plugin-reference/runtime-object#getinstance; https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/object-interfaces/iobjectclass"
    ),

    # --- 边界测试 ---
    BenchmarkCase(
        id="B14",
        category="边界",
        question="Construct 3 支持 WebGPU 渲染吗？有什么限制？",
        expected_keywords=[],
        forbidden_phrases=["完全支持", "没有限制"],
        note="边界知识，防止幻觉",
        has_answer=False
    ),
    BenchmarkCase(
        id="B15",
        category="边界",
        question="Construct 3 r999 版本有哪些新功能？",
        expected_keywords=[],
        forbidden_phrases=["r999"],
        note="不存在的版本，应说明无法找到。并从官方网址(https://www.construct.net/en/make-games/releases) 的版本列表检查最新版本。如最新的测试版本是{0}, 发布于{1}。 最新正式版是{2}, 发布于{3}。",
        has_answer=False
    ),
]


# =============================================================================
# 评分器
# =============================================================================

@dataclass
class EvalResult:
    """单个用例的评估结果"""
    case_id: str
    question: str
    answer: str
    confidence: str
    elapsed: float

    # 评分维度 (0.0 - 1.0)
    keyword_score: float = 0.0      # 关键词覆盖率
    citation_score: float = 0.0     # 引用标注率
    confidence_score: float = 0.0   # 置信度质量
    hallucination_penalty: float = 0.0  # 幻觉惩罚（禁词出现）

    @property
    def total_score(self) -> float:
        base = (self.keyword_score * 0.4 +
                self.citation_score * 0.3 +
                self.confidence_score * 0.3)
        return max(0.0, base - self.hallucination_penalty)

    @property
    def grade(self) -> str:
        s = self.total_score
        if s >= 0.8:
            return "A"
        elif s >= 0.6:
            return "B"
        elif s >= 0.4:
            return "C"
        else:
            return "D"


def score_keywords(answer: str, expected: List[str], case: BenchmarkCase) -> float:
    """关键词覆盖率评分"""
    if not expected:
        if not case.has_answer:
            # 没有预期答案的用例，检查是否有"不知道"类回答
            no_answer_signals = ["未找到", "未提及", "文档", "没有", "无法"]
            hits = sum(1 for s in no_answer_signals if s in answer)
            return min(1.0, hits / 2)
        return 0.5  # 无法评判

    answer_lower = answer.lower()
    hits = sum(1 for kw in expected if kw.lower() in answer_lower)
    return hits / len(expected)


def score_citations(answer: str, case: BenchmarkCase) -> float:
    """引用标注评分 - 检查是否有 [来源: N] 格式"""
    import re

    # Boundary tests (has_answer=False): no citations expected
    if not case.has_answer:
        no_answer_signals = ["未找到", "未提及", "文档", "没有", "无法"]
        if any(s in answer for s in no_answer_signals):
            return 1.0
        return 0.3

    # Match standard [来源: N] and common LLM variations
    citations = re.findall(
        r'\[来源[:：]\s*[\d,\s]+\]'       # [来源: 1] or [来源: 1,2,3]
        r'|来源[:：]\s*\[\d+\]'            # 来源: [2]
        r'|\[来源[:：]\s*\d+',             # [来源: 1 (unclosed)
        answer,
    )
    if len(citations) >= 3:
        return 1.0
    elif len(citations) >= 1:
        return 0.6
    elif "[通用经验]" in answer:
        return 0.3
    else:
        return 0.0


def score_confidence(confidence: str) -> float:
    """置信度质量评分"""
    mapping = {"high": 1.0, "medium": 0.6,
               "low": 0.3, "none": 0.0, "unknown": 0.0}
    return mapping.get(confidence, 0.0)


def score_hallucination(answer: str, forbidden: List[str]) -> float:
    """幻觉惩罚 - 禁词出现则扣分"""
    if not forbidden:
        return 0.0
    answer_lower = answer.lower()
    hits = sum(1 for phrase in forbidden if phrase.lower() in answer_lower)
    return min(0.5, hits * 0.25)


def evaluate_case(case: BenchmarkCase, chain: RAGChain, mode: str) -> EvalResult:
    """对单个用例运行评估"""
    t0 = time.time()

    try:
        if mode == "high":
            response = chain.answer_high_confidence(case.question)
        elif mode == "stream":
            # Collect stream into full text
            chunks = list(chain.answer_stream(case.question))
            full_text = "".join(chunks)
            response = RAGResponse(
                answer=full_text,
                sources=[],
                query_type="stream",
                confidence="unknown"
            )
        else:
            # Default: smart
            response = chain.answer_smart(case.question)

    except Exception as e:
        response = RAGResponse(
            answer=f"[ERROR] {e}",
            sources=[],
            query_type="error",
            confidence="none"
        )

    elapsed = time.time() - t0

    result = EvalResult(
        case_id=case.id,
        question=case.question,
        answer=response.answer,
        confidence=response.confidence,
        elapsed=elapsed,
    )

    result.keyword_score = score_keywords(
        response.answer, case.expected_keywords, case)
    result.citation_score = score_citations(response.answer, case)
    result.confidence_score = score_confidence(response.confidence)
    result.hallucination_penalty = score_hallucination(
        response.answer, case.forbidden_phrases)

    return result


# =============================================================================
# 报告生成
# =============================================================================

def print_progress(case: BenchmarkCase, result: EvalResult):
    """实时打印单个用例结果"""
    grade = result.grade
    grade_symbol = {"A": "✓", "B": "○", "C": "△", "D": "✗"}.get(grade, "?")
    print(
        f"  [{grade_symbol} {grade}] {case.id} ({case.category}) "
        f"kw={result.keyword_score:.1f} "
        f"cite={result.citation_score:.1f} "
        f"conf={result.confidence_score:.1f} "
        f"total={result.total_score:.2f} "
        f"({result.elapsed:.1f}s)"
    )


def generate_report(results: List[EvalResult], cases: List[BenchmarkCase], mode: str) -> str:
    """生成 Markdown 评估报告"""
    total = len(results)
    if total == 0:
        return "# 无评估结果\n"

    avg_total = sum(r.total_score for r in results) / total
    avg_kw = sum(r.keyword_score for r in results) / total
    avg_cite = sum(r.citation_score for r in results) / total
    avg_conf = sum(r.confidence_score for r in results) / total
    avg_time = sum(r.elapsed for r in results) / total

    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        grade_counts[r.grade] = grade_counts.get(r.grade, 0) + 1

    lines = [
        f"# Construct 3 RAG 评估报告",
        f"",
        f"**模式**: `{mode}` | **题数**: {total} | **平均耗时**: {avg_time:.1f}s",
        f"",
        f"## 总体评分",
        f"",
        f"| 维度 | 得分 | 权重 |",
        f"|------|------|------|",
        f"| 关键词覆盖率 | {avg_kw:.2f} | 40% |",
        f"| 引用标注率 | {avg_cite:.2f} | 30% |",
        f"| 置信度质量 | {avg_conf:.2f} | 30% |",
        f"| **综合得分** | **{avg_total:.2f}** | - |",
        f"",
        f"等级分布: A={grade_counts['A']} B={grade_counts['B']} "
        f"C={grade_counts['C']} D={grade_counts['D']}",
        f"",
        f"## 分类统计",
        f"",
    ]

    # Per-category stats
    categories: dict = {}
    case_map = {c.id: c for c in cases}
    for r in results:
        cat = case_map[r.case_id].category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    lines.append("| 分类 | 题数 | 综合 | 关键词 | 引用 | 置信度 |")
    lines.append("|------|------|------|--------|------|--------|")
    for cat, cat_results in sorted(categories.items()):
        n = len(cat_results)
        lines.append(
            f"| {cat} | {n} "
            f"| {sum(r.total_score for r in cat_results)/n:.2f} "
            f"| {sum(r.keyword_score for r in cat_results)/n:.2f} "
            f"| {sum(r.citation_score for r in cat_results)/n:.2f} "
            f"| {sum(r.confidence_score for r in cat_results)/n:.2f} |"
        )

    lines += ["", "## 逐题结果", ""]
    lines.append("| ID | 分类 | 综合 | 等级 | 关键词 | 引用 | 置信度 | 耗时 |")
    lines.append("|----|------|------|------|--------|------|--------|------|")
    for r in results:
        cat = case_map[r.case_id].category
        lines.append(
            f"| {r.case_id} | {cat} "
            f"| {r.total_score:.2f} | {r.grade} "
            f"| {r.keyword_score:.2f} "
            f"| {r.citation_score:.2f} "
            f"| {r.confidence_score:.2f} "
            f"| {r.elapsed:.1f}s |"
        )

    lines += ["", "## 详细回答", ""]
    for r in results:
        case = case_map[r.case_id]
        lines += [
            f"### {r.case_id} [{r.grade}] {case.question}",
            f"",
            f"**置信度**: {r.confidence} | **耗时**: {r.elapsed:.1f}s | **综合**: {r.total_score:.2f}",
            f"",
            f"**回答**:",
            f"",
            f"> {r.answer[:500].replace(chr(10), chr(10)+'> ')}",
            f"",
        ]
        if case.expected_keywords:
            found = [kw for kw in case.expected_keywords if kw.lower()
                     in r.answer.lower()]
            missing = [kw for kw in case.expected_keywords if kw.lower()
                       not in r.answer.lower()]
            if found:
                lines.append(f"✓ 命中关键词: {', '.join(found)}")
            if missing:
                lines.append(f"✗ 缺失关键词: {', '.join(missing)}")
            lines.append("")
        if r.hallucination_penalty > 0:
            found_forbidden = [
                p for p in case.forbidden_phrases if p.lower() in r.answer.lower()]
            lines.append(
                f"⚠ 幻觉警告: 出现禁词 {found_forbidden} (扣分 {r.hallucination_penalty:.2f})")
            lines.append("")

    return "\n".join(lines)


# =============================================================================
# 主程序
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Construct 3 RAG Benchmark")
    parser.add_argument("--mode", default="smart",
                        choices=["smart", "high", "stream"],
                        help="回答模式: smart(默认)/high(高置信度)/stream(流式)")
    parser.add_argument("--output", default="",
                        help="输出报告到文件 (默认: 打印到控制台)")
    parser.add_argument("--cases", default="",
                        help="只运行指定 ID 的题目, 逗号分隔 (如 B01,B02)")
    args = parser.parse_args()

    # Filter cases
    cases = BENCHMARK_CASES
    if args.cases:
        wanted = {c.strip().upper() for c in args.cases.split(",")}
        cases = [c for c in cases if c.id in wanted]
        if not cases:
            print(f"未找到指定题目: {args.cases}")
            sys.exit(1)

    print(f"\nConstruct 3 RAG Benchmark")
    print(f"模式: {args.mode} | 题数: {len(cases)}")
    print(f"连接 Qdrant: {QDRANT_HOST}:{QDRANT_PORT}")
    print(f"LLM: {LLM_PROVIDER}:{LLM_MODEL}")
    print("-" * 60)

    # Init chain
    print("初始化 RAG 系统...")
    chain = RAGChain(
        qdrant_host=QDRANT_HOST,
        qdrant_port=QDRANT_PORT,
        llm_model=LLM_MODEL,
        llm_base_url=LLM_BASE_URL,
        llm_api_key=LLM_API_KEY,
        llm_provider=LLM_PROVIDER,
    )

    # Warm up embedder
    _ = chain.retriever.embedder
    print("就绪\n")

    # Run benchmark
    results: List[EvalResult] = []
    for i, case in enumerate(cases, 1):
        print(f"[{i:2d}/{len(cases)}] {case.id} {case.question[:50]}...")
        result = evaluate_case(case, chain, args.mode)
        results.append(result)
        print_progress(case, result)

    # Generate report
    print("\n" + "=" * 60)
    report = generate_report(results, cases, args.mode)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"报告已保存到: {args.output}")
    else:
        print(report)

    # Summary stats
    avg = sum(r.total_score for r in results) / len(results)
    print(f"\n综合得分: {avg:.2f}/1.00")


if __name__ == "__main__":
    main()
