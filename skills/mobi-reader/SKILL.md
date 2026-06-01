---
name: mobi-reader
description: >
  Parse, analyze, and summarize MOBI ebook files. Extract table of contents,
  chapter content, metadata, generate chapter summaries, and provide comprehensive
  book evaluations. Supports optional integration with Douban (豆瓣) book reviews
  for cross-validation. Use this whenever the user mentions MOBI, Kindle ebooks,
  ebook analysis, or wants to parse/summarize Chinese ebooks.
compatibility: requires calibre (brew install --cask calibre)
license: MIT
metadata:
  version: 2.0.0
  supported_formats: [MOBI, AZW, AZW3, PRC]
  chapter_formats: [第X章, standalone numerals, 序言/导言, 结语/后记, 致谢]
---

# MOBI Reader & Analyzer

Parse MOBI ebook files, extract chapters and content, generate structured summaries,
and provide comprehensive evaluations with optional Douban (豆瓣) cross-referencing.

## Prerequisites

- **calibre** (`brew install --cask calibre`) — provides `ebook-convert` for MOBI→TXT/EPUB conversion
- `ebooklib`, `beautifulsoup4` — auto-installed if missing

## Installation

```bash
# Clone the skills repo
git clone https://github.com/nonumber1989/sevenup-skills.git

# Install to Claude Code (project-level)
cp -r sevenup-skills/skills/mobi-reader .claude/skills/

# Or install globally
cp -r sevenup-skills/skills/mobi-reader ~/.claude/skills/
```

The bundled parser script is at `skills/mobi-reader/scripts/mobi_parser.py` — copy it to your project or add it to PATH.

## Usage Flow

When the user provides a `.mobi` file or asks to analyze one:

### Step 1 — Parse

```bash
python3 scripts/mobi_parser.py "<filepath.mobi>" --chapter-titles
```

Displays metadata, chapter titles with character counts, and total stats.

### Step 2 — Choose Analysis Mode

Present the user with 6 options:

| # | Mode | Description |
|---|------|-------------|
| 1 | 查看目录 | Display detailed table of contents |
| 2 | 章节摘要 | Summarize specific chapters with key points |
| 3 | 全书摘要 | Summarize all chapters and cross-chapter themes |
| 4 | 综合评价 | Structured evaluation (argument quality, originality, readability, utility) |
| 5 | 问答模式 | Answer specific questions by searching chapter content |
| 6 | 豆瓣参考 | Cross-reference with Douban book reviews (ask first) |

### Step 3 — Execute

**TOC**: `python3 scripts/mobi_parser.py "<file.mobi>" --toc`

**Chapter summary**: `python3 scripts/mobi_parser.py "<file.mobi>" --chapter <N>`

For each chapter, provide: key points (3-5 bullets), core arguments, notable quotes, brief summary.

**Full book summary**: Read each main chapter, extract key points, identify cross-chapter themes, synthesize.

**Comprehensive evaluation**:

| Dimension | Criteria |
|-----------|----------|
| 论证质量 | Logic rigor, evidence sufficiency |
| 原创性 | Novel viewpoints or frameworks |
| 可读性 | Language style, structure, translation quality |
| 实用性 | Practical application value |

Output: 1-5 star ratings per dimension, chapter importance ratings, pros/cons, recommended readers.

**Q&A Mode**: Search relevant chapter content:
```bash
python3 scripts/mobi_parser.py "<file.mobi>" --text | grep -i "<keyword>"
```

**Douban Reference**: Ask user permission first, then:
1. `WebSearch`: `"<book_title>" site:book.douban.com`
2. `WebFetch`: Douban book page → extract rating, review count, top reviews
3. Compare with internal evaluation, note discrepancies

## CLI Reference

```
python3 scripts/mobi_parser.py <file.mobi> [options]

Options:
  --json [FILE]      Export book data as JSON
  --toc              Print table of contents
  --chapter N        Print content of chapter N
  --text             Print full text
  --meta             Print metadata only
  --summary          Print chapter summary with bar charts
  --chapter-titles   Print chapter titles with types and char counts (default)
  --keep-temp        Keep temporary conversion files
```

## Python API

```python
from mobi_parser import MOBIParser

parser = MOBIParser('book.mobi')
parser.parse()

# Metadata
print(parser.metadata.title, parser.metadata.author)

# Chapters
for ch in parser.get_chapters():
    print(f'[{ch.index}] [{ch.chapter_type}] {ch.title}: {ch.char_count} chars')

# Get specific chapter content
ch = parser.get_chapter(3)
print(ch.content[:2000])

# Export
parser.to_json('book_analysis.json')
```

## Chapter Types

| Type | Chinese | Examples |
|------|---------|----------|
| `copyright` | 版权信息 | 版权页 |
| `preface` | 序言 | 序言, 导言, 推荐序, 自序, 前言, 楔子 |
| `part` | 分部 | 第一部分, 第二部分 |
| `chapter` | 章节 | 第一章, 一 (standalone numeral) |
| `conclusion` | 结语 | 结语, 结论, 尾声 |
| `acknowledgments` | 致谢 | 致谢, 鸣谢 |
| `postscript` | 后记 | 后记, 跋 |
| `appendix` | 附录 | 附录A |

## Supported Chapter Formats

- Standard: `第X章 标题` (single-line or title on next line)
- Part dividers: `第X部分 标题`, `第一部分 标题`
- Numbered sections: `一 标题` through `十二 标题` (translated non-fiction)
- Preface variants: `序言`, `导言`, `推荐序`, `自序`, `前言`, `楔子`
- Back matter: `结语`, `结论`, `尾声`, `后记`, `跋`, `致谢`, `鸣谢`

## Author Extraction Strategies

1. Standard: `作者：XXX` or `作者: XXX`
2. Slash format: `《BookTitle》/Author著`
3. Legacy format: `《BookTitle》Author` on standalone line
4. EPUB DC metadata (`creator` field)

## Implementation Notes

- For Chinese books, `char_count` is more meaningful than `word_count`
- EPUB TOC provides sub-section headings; stored in `chapter.key_points`
- For chapters >10K chars, read first 2000 + last 1000 chars for summary
- Non-standard formats trigger EPUB TOC-based fallback detection
- Tiny TOC ghost entries (<200 chars) are automatically removed
- Adjacent same-chapter duplicates (quoted/unquoted variants) are deduplicated

## Error Handling

| Error | Action |
|-------|--------|
| `ebook-convert` not found | Install calibre: `brew install --cask calibre` |
| DRM-encrypted MOBI | Cannot process; inform user |
| <3 chapters detected | Auto-fallback to EPUB TOC-based detection |
| Conversion failure | Check file integrity; try alternative | 
| Author "未知" | Uncommon metadata format; check first 20 lines manually |

## Validated Files

| File | Type | Size | Chapters | Status |
|------|------|------|----------|--------|
| 智人之上 | Non-fiction (history/tech) | 1.1 MB | 18 | ✅ |
| 北京法源寺 | Historical novel | 517 KB | 15 | ✅ |
| 毒品史 | Non-fiction (politics) | 848 KB | 15 | ✅ |
| 增长黑客 | Business/tech | 7.3 MB | 11 | ✅ |
