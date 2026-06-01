# sevenup-skills

Claude Code skills collection — pluggable modules that extend Claude Code with specialized domain knowledge and tooling.

## Skills

### mobi-reader (v2.0.0)

Parse, analyze, and summarize MOBI ebook files. Designed for Chinese Kindle ebooks.

**Capabilities**: TOC extraction, chapter detection (8 format variants), metadata parsing, chapter-level summarization, comprehensive evaluation with 5-dimension scoring, Douban (豆瓣) cross-referencing.

**Validated on**: 《智人之上》《北京法源寺》《毒品史》《增长黑客》— novels, history, business non-fiction.

**Prerequisites**: calibre (`brew install --cask calibre`)

## Installation

### Option 1: Install the .skill package

```bash
git clone https://github.com/nonumber1989/sevenup-skills.git
```

In Claude Code, install the packaged skill:
```
/plugin install sevenup-skills/mobi-reader.skill
```

### Option 2: Manual install

```bash
git clone https://github.com/nonumber1989/sevenup-skills.git

# Copy SKILL.md + scripts to your project or global skills
cp -r sevenup-skills/mobi-reader ~/.claude/skills/
```

## Usage

```bash
# Parse a MOBI file
python3 mobi-reader/scripts/mobi_parser.py book.mobi --chapter-titles

# Export all data as JSON
python3 mobi-reader/scripts/mobi_parser.py book.mobi --json output.json
```

See [SKILL.md](./mobi-reader/SKILL.md) for full documentation.

## License

MIT
