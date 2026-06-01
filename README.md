# sevenup-skills

Claude Code skills collection — pluggable modules that extend Claude Code with specialized domain knowledge and tooling.

## Skills

### mobi-reader (v2.0.0)

Parse, analyze, and summarize MOBI ebook files. Ideal for Chinese Kindle ebooks.

**Capabilities**: TOC extraction, chapter detection (8 format variants), metadata parsing, chapter-level summarization, comprehensive evaluation with 5-dimension scoring, Douban (豆瓣) cross-referencing.

**Supported chapter formats**: `第X章`, `第X部分`, standalone numerals (`一`~`十二`), `序言/导言/推荐序/自序/前言`, `结语/结论/后记`, `致谢`.

**Prerequisites**: calibre (`brew install --cask calibre`)

[Documentation](./mobi-reader/mobi-reader.md) · [Parser Script](./mobi-reader/scripts/mobi_parser.py)

## Installation

```bash
git clone https://github.com/nonumber1989/sevenup-skills.git

# Project-level (single project)
cp sevenup-skills/mobi-reader/mobi-reader.md <project>/.claude/skills/

# Global (all projects)
cp sevenup-skills/mobi-reader/mobi-reader.md ~/.claude/skills/
```

## License

MIT
