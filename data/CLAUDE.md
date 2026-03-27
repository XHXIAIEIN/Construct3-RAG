# data/ Directory

Pre-built Construct 3 API definitions. Committed to git, no setup needed.

| Directory | Content |
|-----------|---------|
| `c3-schemas/_index.json` | Plugin/behavior/effect index (language-neutral) |
| `c3-schemas/en/` | English schema files (plugins, behaviors, effects, editor) |
| `c3-schemas/zh/` | Chinese schema files (same structure, localized text) |
| `c3-schemas/{lang}/examples/` | 481 example projects with localized tags and used addons |
| `c3-ts-defs/` | TypeScript scripting interfaces (from CDN) |
| `c3-ts-defs/autocomplete-data.json` | Class → method/property listings |

Schema files use CDN-native field names: `list-name`, `display-text`, `translated-name` (expressions).
Structural fields (`id`, `scriptName`, `category`, `params.*.type`) are identical across languages.

Updated automatically by GitHub Action on new Construct 3 releases.
