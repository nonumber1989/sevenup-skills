#!/usr/bin/env python3
"""
MOBI Ebook Parser & Analyzer

Parses MOBI ebook files using calibre's ebook-convert for reliable conversion,
extracts metadata, table of contents, chapters with clean text content,
and provides interfaces for summarization and evaluation.

Dependencies:
  - calibre (brew install --cask calibre) - provides ebook-convert
  - ebooklib - for EPUB TOC parsing
  - beautifulsoup4 - for HTML parsing (optional)
"""

import subprocess
import os
import re
import sys
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import OrderedDict


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class BookMetadata:
    """Book metadata extracted from MOBI/EPUB."""
    title: str = ""
    full_title: str = ""
    author: str = ""
    translator: str = ""
    publisher: str = ""
    isbn: str = ""
    asin: str = ""
    publish_date: str = ""
    language: str = ""
    description: str = ""
    subject: str = ""
    rights: str = ""


@dataclass
class Chapter:
    """Represents a chapter/section in the book."""
    index: int
    title: str
    level: int = 1          # 0=frontmatter, 1=chapter, 2=part, 3=sub-chapter
    chapter_type: str = ""  # 'cover','copyright','dedication','preface','part','chapter','conclusion','acknowledgments'
    anchor: str = ""
    content: str = ""
    word_count: int = 0
    char_count: int = 0
    summary: str = ""       # populated after summarization
    key_points: List[str] = field(default_factory=list)


# ============================================================================
# MOBI Parser
# ============================================================================

class MOBIParser:
    """
    Parse a MOBI ebook file into structured chapters and metadata.

    Uses calibre's ebook-convert for reliable MOBI decompression and
    ebooklib for EPUB TOC parsing.

    Usage:
        parser = MOBIParser('book.mobi')
        parser.parse()

        print(parser.metadata.title)
        for ch in parser.chapters:
            print(f'[{ch.index}] {ch.title}: {ch.word_count} words')

        # Get chapter content
        ch0 = parser.get_chapter(0)
        print(ch0.content[:500])
    """

    def __init__(self, filepath: str, work_dir: str = None):
        """
        Args:
            filepath: Path to the MOBI file
            work_dir: Working directory for temp files (default: system temp)
        """
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"MOBI file not found: {filepath}")

        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix='mobi_parser_'))
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self.metadata = BookMetadata()
        self.chapters: List[Chapter] = []
        self._toc_entries: List[Dict] = []
        self._full_text: str = ""
        self._parsed = False

        # Paths for converted files
        self._txt_path = self.work_dir / 'book.txt'
        self._epub_path = self.work_dir / 'book.epub'

    # ========================================================================
    # Public API
    # ========================================================================

    def parse(self, cleanup: bool = False) -> 'MOBIParser':
        """
        Parse the MOBI file. Returns self for chaining.

        Args:
            cleanup: If True, remove temp files after parsing
        """
        print(f"Parsing: {self.filepath.name}")

        # Step 1: Convert MOBI to TXT using calibre
        print("  Converting to TXT...")
        self._convert_to_txt()

        # Step 2: Convert MOBI to EPUB for TOC extraction
        print("  Converting to EPUB for TOC...")
        self._convert_to_epub()

        # Step 3: Extract TOC from EPUB
        print("  Extracting table of contents...")
        self._extract_toc()

        # Step 4: Parse metadata
        print("  Extracting metadata...")
        self._extract_metadata()

        # Step 5: Split text into chapters
        print("  Splitting into chapters...")
        self._split_chapters()

        # Step 6: Load full text
        self._full_text = self._txt_path.read_text(encoding='utf-8') if self._txt_path.exists() else ""

        self._parsed = True

        if cleanup:
            self.cleanup()

        print(f"  Done! {len(self.chapters)} chapters/sections found, "
              f"{sum(c.word_count for c in self.chapters):,} total words")
        return self

    def cleanup(self):
        """Remove temporary files."""
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir, ignore_errors=True)

    def get_metadata(self) -> BookMetadata:
        """Return parsed metadata."""
        if not self._parsed:
            self.parse()
        return self.metadata

    def get_toc(self) -> List[Dict]:
        """Get the table of contents."""
        if not self._parsed:
            self.parse()
        return self._toc_entries

    def get_chapters(self) -> List[Chapter]:
        """Get all parsed chapters with content."""
        if not self._parsed:
            self.parse()
        return self.chapters

    def get_chapter(self, index: int) -> Optional[Chapter]:
        """Get a specific chapter by index."""
        if not self._parsed:
            self.parse()
        if 0 <= index < len(self.chapters):
            return self.chapters[index]
        return None

    def get_chapter_by_title(self, title: str, fuzzy: bool = True) -> Optional[Chapter]:
        """Find a chapter by title (exact or fuzzy match)."""
        if not self._parsed:
            self.parse()
        for ch in self.chapters:
            if fuzzy and title in ch.title:
                return ch
            if ch.title == title:
                return ch
        return None

    def get_full_text(self) -> str:
        """Get the full plain text content."""
        if not self._parsed:
            self.parse()
        return self._full_text

    def get_chapter_content_range(self, start: int, end: int = None) -> str:
        """Get combined text content of a range of chapters."""
        if not self._parsed:
            self.parse()
        if end is None:
            end = start + 1
        chs = self.chapters[start:end]
        return '\n\n'.join(
            f"## {c.title}\n\n{c.content}" for c in chs if c.content
        )

    def get_main_chapters(self) -> List[Chapter]:
        """Get only the main content chapters (exclude front/back matter)."""
        if not self._parsed:
            self.parse()
        return [c for c in self.chapters
                if c.chapter_type in ('chapter', 'part', 'preface', 'conclusion')]

    def to_dict(self) -> Dict:
        """Export book data as a dictionary."""
        if not self._parsed:
            self.parse()
        return {
            'metadata': {
                'title': self.metadata.title,
                'full_title': self.metadata.full_title,
                'author': self.metadata.author,
                'translator': self.metadata.translator,
                'publisher': self.metadata.publisher,
                'isbn': self.metadata.isbn,
                'asin': self.metadata.asin,
                'publish_date': self.metadata.publish_date,
                'language': self.metadata.language,
            },
            'toc': self._toc_entries,
            'chapters': [
                {
                    'index': c.index,
                    'title': c.title,
                    'level': c.level,
                    'type': c.chapter_type,
                    'word_count': c.word_count,
                    'char_count': c.char_count,
                    'content_preview': c.content[:300] + '...' if len(c.content) > 300 else c.content,
                }
                for c in self.chapters
            ],
            'stats': {
                'total_chapters': len(self.chapters),
                'main_chapters': len(self.get_main_chapters()),
                'total_words': sum(c.word_count for c in self.chapters),
                'total_chars': sum(c.char_count for c in self.chapters),
            }
        }

    def to_json(self, filepath: str = None) -> str:
        """Export as JSON string or write to file."""
        data = self.to_dict()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        if filepath:
            Path(filepath).write_text(json_str, encoding='utf-8')
        return json_str

    # ========================================================================
    # Conversion
    # ========================================================================

    def _convert_to_txt(self):
        """Convert MOBI to TXT using calibre's ebook-convert."""
        cmd = [
            'ebook-convert',
            str(self.filepath),
            str(self._txt_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not self._txt_path.exists():
            raise RuntimeError(f"TXT conversion failed: {result.stderr[:500]}")

    def _convert_to_epub(self):
        """Convert MOBI to EPUB for TOC extraction."""
        cmd = [
            'ebook-convert',
            str(self.filepath),
            str(self._epub_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not self._epub_path.exists():
            print(f"  Warning: EPUB conversion failed, using TXT-based TOC only")
            self._epub_path = None

    # ========================================================================
    # TOC Extraction
    # ========================================================================

    def _extract_toc(self):
        """Extract table of contents from EPUB or fall back to TXT parsing."""
        self._toc_entries = []

        # Try EPUB TOC first
        if self._epub_path and self._epub_path.exists():
            try:
                self._toc_entries = self._extract_epub_toc()
                if self._toc_entries:
                    return
            except Exception as e:
                print(f"  EPUB TOC extraction failed: {e}")

        # Fall back to TXT-based TOC detection
        self._toc_entries = self._detect_toc_from_text()

    def _extract_epub_toc(self) -> List[Dict]:
        """Extract TOC from EPUB file using ebooklib."""
        from ebooklib import epub

        book = epub.read_epub(str(self._epub_path))
        entries = []

        def process_item(item, level=0):
            if isinstance(item, tuple) and len(item) >= 2:
                # Section with children
                section = item[0]
                children = item[1]
                if hasattr(section, 'title') and section.title:
                    entries.append({
                        'title': section.title.strip(),
                        'level': level,
                        'children_count': len(children) if isinstance(children, list) else 0,
                    })
                if isinstance(children, list):
                    for child in children:
                        process_item(child, level + 1)
            elif hasattr(item, 'title') and item.title:
                # Single link
                entries.append({
                    'title': item.title.strip(),
                    'level': level,
                    'children_count': 0,
                })

        for item in book.toc:
            process_item(item, 0)

        return entries

    def _detect_toc_from_text(self) -> List[Dict]:
        """Detect chapter structure from TXT content using heuristics."""
        if not self._txt_path.exists():
            return []

        text = self._txt_path.read_text(encoding='utf-8')
        entries = []

        # Common Chinese chapter patterns
        patterns = [
            (r'^第([一二三四五六七八九十百千\d]+)章\s*[^\n]+', 1, 'chapter'),
            (r'^第([一二三四五六七八九十百千\d]+)部分\s*[^\n]+', 0, 'part'),
            (r'^序言\s*$', 2, 'preface'),
            (r'^结语\s*$', 2, 'conclusion'),
            (r'^致谢\s*$', 2, 'acknowledgments'),
            (r'^后记\s*$', 2, 'postscript'),
            (r'^版权信息\s*$', 2, 'copyright'),
        ]

        for line in text.split('\n'):
            line = line.strip()
            if not line or len(line) > 100:
                continue

            for pattern, level, ctype in patterns:
                match = re.match(pattern, line)
                if match:
                    entries.append({
                        'title': line,
                        'level': level,
                    })
                    break

        return entries

    # ========================================================================
    # Metadata Extraction
    # ========================================================================

    def _extract_metadata(self):
        """Extract metadata from TXT front matter and EPUB metadata."""
        # Parse from TXT front matter
        if self._txt_path.exists():
            text = self._txt_path.read_text(encoding='utf-8')

            # Extract metadata from copyright section
            meta_patterns = {
                'full_title': r'书名[:：]\s*([^\n]+)',
                'author': r'作者[:：]\s*([^\n]+)',
                'translator': r'译者[:：]\s*([^\n]+)',
                'publish_date': r'出版时间[:：]\s*([^\n]+)',
                'isbn': r'ISBN[:：]\s*([^\n]+)',
                'publisher': r'([^\n]+出版[社集团][^\n]*)',
            }

            for field, pattern in meta_patterns.items():
                match = re.search(pattern, text[:5000])
                if match:
                    value = match.group(1).strip()
                    setattr(self.metadata, field, value)

            # Fallback: Try "《书名》作者名" format on first few lines
            if not self.metadata.author:
                first_lines = '\n'.join(text.split('\n')[:20])
                # Match patterns like:
                # 《北京法源寺》李敖
                # 增长黑客：创业公司的用户与收入增长秘籍/范冰著．—北京...
                # 作者：张三
                author_patterns = [
                    r'《[^》]+》\s*([^\n]{2,20})\s*$',
                    r'/([^/\s]{1,20})\s*(?:著|编著|主编|编)\b',
                    r'作者\s*[:：]?\s*([^\n]{2,30})',
                    r'(?:^|[^\S\n]{0,5})([^\n]{2,20})\s*(著|编著|主编)\s',
                    r'^([^\n]{2,20})\s*(著|编著|主编)\s*$',
                ]
                for ap in author_patterns:
                    am = re.search(ap, first_lines, re.MULTILINE)
                    if am:
                        candidate = am.group(1).strip()
                        # Remove leading path separators
                        candidate = re.sub(r'^.*/', '', candidate)
                        # Reject pure numbers, dates, or very long strings
                        if len(candidate) >= 2 and len(candidate) <= 20 and not re.match(r'^[\d\s\-/.]+$', candidate):
                            if candidate not in ('未经许可', '版权所有', '图书在版', '内容简介'):
                                self.metadata.author = candidate
                                break

            # Fallback: Extract title from "《书名》" format if not found
            if not self.metadata.full_title and not self.metadata.title:
                title_match = re.search(r'《([^》]+)》', text[:2000])
                if title_match:
                    self.metadata.full_title = title_match.group(1)

        # Try to get metadata from EPUB
        if self._epub_path and self._epub_path.exists():
            try:
                from ebooklib import epub
                book = epub.read_epub(str(self._epub_path))
                dc = book.get_metadata('DC', {})
                if not self.metadata.title:
                    titles = book.get_metadata('DC', 'title')
                    if titles:
                        self.metadata.title = titles[0][0]
                if not self.metadata.author:
                    creators = book.get_metadata('DC', 'creator')
                    if creators:
                        self.metadata.author = creators[0][0]
                if not self.metadata.language:
                    langs = book.get_metadata('DC', 'language')
                    if langs:
                        self.metadata.language = langs[0][0]
            except Exception:
                pass

        # Set title from full_title if title is empty
        if not self.metadata.title:
            self.metadata.title = self.metadata.full_title or self.filepath.stem

    # ========================================================================
    # Chapter Splitting
    # ========================================================================

    def _split_chapters(self):
        """Split the full text into chapters.

        Strategy:
        1. Detect chapter positions using regex patterns in the text
        2. Cross-reference detected chapters with EPUB TOC for full titles
        3. Skip TOC/index pages at the end of the book
        4. Extract content between chapter boundaries
        """
        if not self._txt_path.exists():
            return

        text = self._txt_path.read_text(encoding='utf-8')

        if not self._toc_entries:
            ch = Chapter(
                index=0, title=self.metadata.title or "Full Text",
                level=1, chapter_type='full', content=text,
                word_count=len(text.split()), char_count=len(text),
            )
            self.chapters.append(ch)
            return

        # Step 1: Detect chapter positions using regex patterns
        # These patterns match Chinese book chapter headings on standalone lines
        # Chapter headings appear as: blank lines + "第一章" + blank lines + "subtitle" + blank lines
        chapter_patterns = [
            # Match standalone "第X章" on its own line (short form, followed by subtitle on next lines)
            (r'(?:^|\n)\s*\n+\s*(第[一二三四五六七八九十百千\d]+章)\s*\n+([^\n]+)', 'chapter', 1),
            # Match full form "第X章 标题" on one line
            (r'(?:^|\n)\s*\n+\s*(第[一二三四五六七八九十百千\d]+章\s+[^\n]+)', 'chapter', 1),
            # Match standalone "第X部分" on own line
            (r'(?:^|\n)\s*\n+\s*(第[一二三四五六七八九十百千\d]+部分)\s*\n+([^\n]+)', 'part', 0),
            # Match full form "第X部分 标题"
            (r'(?:^|\n)\s*\n+\s*(第[一二三四五六七八九十百千\d]+部分\s+[^\n]+)', 'part', 0),
            # Structural sections - preface/introduction variants
            (r'(?:^|\n)\s*\n+\s*(序言|导言)\s*\n+([^\n]+)', 'preface', 1),
            (r'(?:^|\n)\s*\n+\s*(序言|导言)\s*\n', 'preface', 1),
            (r'(?:^|\n)\s*\n+\s*(结语|结论|尾声)\s*\n', 'conclusion', 1),
            (r'(?:^|\n)\s*\n+\s*(致谢|鸣谢)\s*\n', 'acknowledgments', 1),
            (r'(?:^|\n)\s*\n+\s*(后记|跋)\s*\n+([^\n]+)', 'postscript', 1),
            (r'(?:^|\n)\s*\n+\s*(后记|跋)\s*\n', 'postscript', 1),
            # Additional preface types
            (r'(?:^|\n)\s*\n+\s*(推荐序|自序|前言|楔子)\s*\n', 'preface', 1),
            # Numbered sections without 第-章 wrapper: "一 标题" through "十二 标题"
            # These must be standalone lines with exactly the number + space + title
            (r'(?:^|\n)\s*\n+\s*([一二三四五六七八九十])\s+([^\n]{2,60})\s*\n', 'chapter', 1),
            # Two-character numbers: 十一, 十二, etc.
            (r'(?:^|\n)\s*\n+\s*(十一|十二|十三|十四|十五|十六|十七|十八|十九|二十)\s+([^\n]{2,60})\s*\n', 'chapter', 1),
        ]

        all_matches = []  # (position, matched_text, type, level)
        seen_positions = set()

        for pattern, ctype, level in chapter_patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                pos = match.start()
                # Skip TOC/index pages: entries that are part of a dense
                # cluster (3+ chapter-like titles within 500 chars after match)
                surrounding = text[pos:pos+500]
                quick_chapter_count = len(re.findall(
                    r'(?:第[一二三四五六七八九十百千\d]+[章部分])|序言|导言|结语|结论|尾声|致谢|鸣谢|后记|跋|推荐序|自序|前言|楔子'
                    r'|\n\s*[一二三四五六七八九十]+\s+[^\n]{2,60}',
                    surrounding
                ))
                if quick_chapter_count >= 3:
                    continue  # TOC/index page cluster
                # Avoid duplicates at same position
                if pos in seen_positions:
                    continue
                seen_positions.add(pos)

                matched_text = match.group(1).strip()
                # For patterns with two groups (short heading + subtitle), combine them
                if len(match.groups()) >= 2 and match.group(2):
                    subtitle = match.group(2).strip()
                    # Only add subtitle if it looks like a title (not body text)
                    if len(subtitle) < 80 and not re.match(r'^[，。、；：！？,.;:!?\d]', subtitle):
                        matched_text = f"{matched_text} {subtitle}"

                all_matches.append((pos, matched_text, ctype, level))

        # Sort by position
        all_matches.sort(key=lambda x: x[0])

        # Remove duplicates: same position from different patterns
        filtered_matches = []
        for match in all_matches:
            is_dup = False
            for existing in filtered_matches:
                if abs(match[0] - existing[0]) < 20 and match[1] == existing[1]:
                    is_dup = True
                    break
            if not is_dup:
                filtered_matches.append(match)
        all_matches = filtered_matches

        # Filter TOC/index entries: TOC entries are densely clustered.
        # Real chapters have large gaps (> 500 chars) to at least one neighbor.
        # TOC entries have small gaps to BOTH neighbors, OR are the last entry
        # with a very small backward gap (end-of-book TOC cluster tail).
        real_matches = []
        for i, (pos, title, ctype, level) in enumerate(all_matches):
            forward_gap = all_matches[i + 1][0] - pos if i + 1 < len(all_matches) else float('inf')
            backward_gap = pos - all_matches[i - 1][0] if i > 0 else float('inf')

            # Case 1: Small gaps on both sides → TOC cluster interior
            if forward_gap < 500 and backward_gap < 500:
                continue

            # Case 2: Last entry with small backward gap AND very little remaining text
            if forward_gap == float('inf') and backward_gap < 500 and (len(text) - pos) < 500:
                continue

            # Case 3: First entry in TOC cluster (small forward gap, not near start of book)
            if forward_gap < 200 and backward_gap > 500 and pos > len(text) * 0.9:
                continue

            # Case 4: Last entry with small backward gap, near end of book (final TOC cluster tail)
            if forward_gap == float('inf') and backward_gap < 500 and pos > len(text) * 0.8:
                continue

            real_matches.append((pos, title, ctype, level))
        all_matches = real_matches

        # Fallback: If regex found very few chapters but TOC has many entries,
        # use TOC-based searching to locate chapter positions
        if len(all_matches) < 3 and len(self._toc_entries) > 3:
            print(f"  Regex found only {len(all_matches)} chapters, "
                  f"falling back to TOC-based detection...")
            toc_matches = self._detect_chapters_from_toc(text)
            # Merge with existing regex matches, avoid duplicates
            existing_positions = {m[0] for m in all_matches}
            for pos, title, ctype, level in toc_matches:
                # Check if this position is already covered (within 100 chars)
                if not any(abs(pos - ep) < 100 for ep in existing_positions):
                    all_matches.append((pos, title, ctype, level))
                    existing_positions.add(pos)
            all_matches.sort(key=lambda x: x[0])
            # Re-apply TOC filtering on merged matches
            all_matches = self._filter_toc_pages(all_matches, text)

        # Deduplicate adjacent same-chapter entries (same base number, within 200 chars)
        # e.g. "第三章 休懷粉身念" vs "第三章 「休懷粉身念」"
        deduped_matches = []
        skip_next = False
        for i, (pos, title, ctype, level) in enumerate(all_matches):
            if skip_next:
                skip_next = False
                continue
            if i + 1 < len(all_matches):
                next_pos, next_title, next_ctype, next_level = all_matches[i + 1]
                # Check if same chapter type and number base, and very close
                gap = next_pos - pos
                if gap < 200 and ctype == next_ctype:
                    # Extract base chapter number (e.g. "第三章" from longer title)
                    base_current = re.match(r'(第[一二三四五六七八九十百千\d]+[章部分])', title)
                    base_next = re.match(r'(第[一二三四五六七八九十百千\d]+[章部分])', next_title)
                    if base_current and base_next and base_current.group(1) == base_next.group(1):
                        # Keep the one with richer title (longer, with quotes, etc.)
                        if len(next_title) > len(title):
                            deduped_matches.append((next_pos, next_title, next_ctype, next_level))
                        else:
                            deduped_matches.append((pos, title, ctype, level))
                        skip_next = True
                        continue
            deduped_matches.append((pos, title, ctype, level))
        all_matches = deduped_matches

        # Step 2: Cross-reference with EPUB TOC to get full titles
        for i, (pos, matched_title, ctype, level) in enumerate(all_matches):
            full_title = self._find_full_title(matched_title, ctype)
            if full_title and len(full_title) > len(matched_title):
                all_matches[i] = (pos, full_title, ctype, level)

        # Step 3: Build chapter objects with content
        self.chapters = []

        # Handle pre-content (before first chapter)
        if all_matches and all_matches[0][0] > 100:
            pre_text = text[:all_matches[0][0]].strip()
            # Try to extract copyright info as a separate section
            copyright_match = re.search(r'(?:^|\n)(版权信息[^\n]*)', pre_text)
            if copyright_match:
                cp_pos = copyright_match.start()
                cp_title = copyright_match.group(1).strip()
                cp_content = text[cp_pos:all_matches[0][0]].strip()
                self.chapters.append(Chapter(
                    index=0, title='版权信息', level=0,
                    chapter_type='copyright', content=cp_content,
                    word_count=len(cp_content.split()),
                    char_count=len(cp_content),
                ))

        for i, (pos, title, ctype, level) in enumerate(all_matches):
            start_pos = pos
            if i + 1 < len(all_matches):
                end_pos = all_matches[i + 1][0]
            else:
                end_pos = len(text)

            # Extract chapter content
            content = text[start_pos:end_pos].strip()
            # Remove the title line
            content_lines = content.split('\n', 1)
            actual_content = content_lines[1].strip() if len(content_lines) > 1 else ""

            ch = Chapter(
                index=len(self.chapters),
                title=title,
                level=level,
                chapter_type=ctype,
                content=actual_content,
                word_count=len(actual_content.split()) if actual_content else 0,
                char_count=len(actual_content),
            )
            self.chapters.append(ch)

        # Step 4: Re-index
        for i, ch in enumerate(self.chapters):
            ch.index = i

        # Step 5: Remove tiny TOC duplicates (chapters with very small content
        # that share the same type+title base with a larger chapter)
        self._remove_tiny_duplicates()

        # Update TOC entries
        self._update_toc_indices()

    def _detect_chapters_from_toc(self, text: str) -> List[Tuple]:
        """Fallback: detect chapters by fuzzy matching TOC titles in text."""
        matches = []
        seen_positions = set()

        for entry in self._toc_entries:
            title = entry['title']
            ctype = self._classify_chapter_type(title)

            # Skip entries that are clearly not chapters
            if ctype == 'sub_section':
                continue

            matched = False

            # Strategy 1: Try exact match
            escaped = re.escape(title)
            for m in re.finditer(rf'(?:^|\n)\s*{escaped}\s*(?:\n|$)', text, re.MULTILINE):
                pos = m.start()
                if pos not in seen_positions and not any(abs(pos - ep) < 50 for ep in seen_positions):
                    matches.append((pos, title, ctype, entry.get('level', 1)))
                    seen_positions.add(pos)
                    matched = True
                    break

            if matched:
                continue

            # Strategy 2: For numbered sections like "一 标题", match "一" + "标题"
            parts = title.replace('　', ' ').split(None, 1)
            if len(parts) >= 2 and len(parts[0]) <= 4:
                num_part = re.escape(parts[0])
                title_part = re.escape(parts[1][:10])
                pattern = rf'(?:^|\n)\s*{num_part}\s+{title_part}'
                for m in re.finditer(pattern, text, re.MULTILINE):
                    pos = m.start()
                    if pos not in seen_positions and not any(abs(pos - ep) < 50 for ep in seen_positions):
                        matches.append((pos, title, ctype, entry.get('level', 1)))
                        seen_positions.add(pos)
                        matched = True
                        break

            if matched:
                continue

            # Strategy 3: Try matching first 6 chars
            short = title[:6].strip()
            if len(short) >= 2:
                escaped_short = re.escape(short)
                for m in re.finditer(rf'(?:^|\n)\s*{escaped_short}', text, re.MULTILINE):
                    pos = m.start()
                    if pos not in seen_positions and not any(abs(pos - ep) < 50 for ep in seen_positions):
                        matches.append((pos, title, ctype, entry.get('level', 1)))
                        seen_positions.add(pos)
                        break

        matches.sort(key=lambda x: x[0])
        return matches

    def _filter_toc_pages(self, matches: List[Tuple], text: str) -> List[Tuple]:
        """Filter out matches that appear in TOC/index pages at the end of the book.

        When chapter titles appear in a clustered section (like a book index),
        they are likely TOC/index pages, not actual chapter starts.
        """
        if len(matches) <= 3:
            return matches

        # Find clusters of matches (likely TOC pages)
        # A cluster has many matches in a short span
        clusters = []
        cluster_start = 0
        for i in range(1, len(matches)):
            gap = matches[i][0] - matches[i-1][0]
            if gap > 5000:  # Large gap = new cluster
                clusters.append((cluster_start, i - 1))
                cluster_start = i
        clusters.append((cluster_start, len(matches) - 1))

        # The real content chapters should be the first cluster
        # TOC pages are typically at the end
        if len(clusters) >= 2:
            # The first (or first few) clusters are real chapters
            # The last cluster(s) are likely TOC/index pages
            # Take the first set of chapters that aren't tightly clustered
            result = []
            for start, end in clusters:
                span = matches[end][0] - matches[start][0]
                count = end - start + 1
                # If this cluster has chapters spread across a large text span,
                # it's likely real content
                avg_gap = span / max(count - 1, 1) if count > 1 else 0
                text_span = text.find('\n', matches[start][0])
                remaining_text = len(text) - matches[start][0]
                # Real chapters: large avg gap or near the start of the book
                if avg_gap > 3000 or matches[start][0] < len(text) * 0.3:
                    result.extend(matches[start:end+1])

            if result:
                return result

        return matches

    def _find_full_title(self, short_title: str, ctype: str) -> str:
        """Find the full chapter title from EPUB TOC by matching the short form."""
        # Extract chapter number for matching (e.g., "第一章" from "第一章 信息是什么？")
        chapter_num_match = re.match(r'(第[一二三四五六七八九十百千\d]+[章部分])', short_title)
        if chapter_num_match:
            chapter_num = chapter_num_match.group(1)
            for entry in self._toc_entries:
                if entry['title'].startswith(chapter_num):
                    return entry['title']

        # For preface, conclusion etc, try to find matching TOC entry
        for entry in self._toc_entries:
            if entry['title'] == short_title or entry['title'].startswith(short_title):
                return entry['title']

        return short_title

    def _identify_main_entries(self) -> List[Dict]:
        """Identify main chapter entries from TOC, filtering out sub-sections.

        Main entries are those that match chapter patterns or are at the top level.
        Also includes level-0 entries that are structural (封面, 版权信息, etc.).
        """
        main = []

        for i, entry in enumerate(self._toc_entries):
            title = entry['title']
            level = entry.get('level', 0)
            ctype = self._classify_chapter_type(title)

            # Always include structural entries
            if ctype in ('cover', 'copyright', 'dedication', 'acknowledgments'):
                main.append({**entry, 'toc_index': i, 'guessed_type': ctype})
                continue

            # Include major chapter markers
            if ctype in ('chapter', 'part', 'preface', 'conclusion', 'postscript', 'appendix'):
                main.append({**entry, 'toc_index': i, 'guessed_type': ctype})
                continue

            # Level-0 entries that aren't sub-sections (part headers, etc.)
            if level == 0 and ctype not in ('chapter', 'sub_section'):
                main.append({**entry, 'toc_index': i, 'guessed_type': ctype})
                continue

        # If we only found a few main entries, include top-level entries
        if len(main) < 3:
            main = []
            for i, entry in enumerate(self._toc_entries):
                if entry.get('level', 0) <= 1:
                    main.append({**entry, 'toc_index': i,
                                 'guessed_type': self._classify_chapter_type(entry['title'])})

        return main

    def _classify_chapter_type(self, title: str) -> str:
        """Classify a chapter title into its type."""
        if any(w in title for w in ['封面', 'cover', 'Cover']):
            return 'cover'
        if any(w in title for w in ['版权', 'copyright']):
            return 'copyright'
        if any(w in title for w in ['献辞', 'dedication', '献给']):
            return 'dedication'
        if any(w in title for w in ['序言', '导言', '推荐序', '自序', '前言', '楔子', 'preface', 'foreword', '引言']):
            return 'preface'
        if any(w in title for w in ['结语', '结论', 'conclusion', '尾声']):
            return 'conclusion'
        if any(w in title for w in ['致谢', 'acknowledg', '鸣谢']):
            return 'acknowledgments'
        if any(w in title for w in ['附录', 'appendix']):
            return 'appendix'
        if any(w in title for w in ['后记', 'postscript', '跋']):
            return 'postscript'
        if re.match(r'^第[一二三四五六七八九十百千\d]+部分', title):
            return 'part'
        if re.match(r'^第[一二三四五六七八九十百千\d]+章', title):
            return 'chapter'
        # For non-matching sub-section titles
        if re.match(r'^第[一二三四五六七八九十百千\d]+', title):
            return 'chapter'
        # Standalone Chinese numerals as section markers
        if re.match(r'^[一二三四五六七八九十]+[、，。\s]', title):
            return 'chapter'
        return 'sub_section'

    def _get_sub_sections(self, toc_index: int) -> List[Dict]:
        """Get sub-section TOC entries that belong to a main chapter entry.

        Sub-sections are entries between this main entry and the next main entry
        that have a higher level.
        """
        # Find the next main entry
        main_indices = {e.get('toc_index', -1) for e in self._identify_main_entries()}

        # Find next main entry index after toc_index
        sorted_mains = sorted(main_indices)
        next_main = None
        for m in sorted_mains:
            if m > toc_index:
                next_main = m
                break

        # Collect sub-sections between this entry and next main entry
        subs = []
        for i, entry in enumerate(self._toc_entries):
            if i > toc_index and (next_main is None or i < next_main):
                if entry.get('level', 0) > 0:  # higher level = sub-section
                    subs.append(entry)

        return subs

    def _remove_tiny_duplicates(self):
        """Remove chapters with very small content that duplicate a larger chapter.

        TOC/index pages at the beginning or end of a book can produce tiny
        chapter entries (e.g. "致谢" with 30 chars next to "致谢" with 55K chars).
        These are false positives from TOC listings.
        """
        if len(self.chapters) <= 3:
            return

        # Build a map of (type, title_base) -> list of indices
        groups = {}
        for i, ch in enumerate(self.chapters):
            # Extract base identifier: chapter number or title prefix
            base = ch.title[:12]  # first 12 chars as grouping key
            key = (ch.chapter_type, base)
            if key not in groups:
                groups[key] = []
            groups[key].append(i)

        # Find groups where one entry is tiny (< 200 chars) and another is substantial
        indices_to_remove = set()
        for key, indices in groups.items():
            if len(indices) >= 2:
                max_chars = max(self.chapters[i].char_count for i in indices)
                min_chars = min(self.chapters[i].char_count for i in indices)
                if min_chars < 200 and max_chars > min_chars * 5:
                    # Remove the tiny one(s)
                    for i in indices:
                        if self.chapters[i].char_count < 200:
                            indices_to_remove.add(i)

        # Remove marked chapters
        if indices_to_remove:
            self.chapters = [ch for i, ch in enumerate(self.chapters)
                             if i not in indices_to_remove]
            # Re-index
            for i, ch in enumerate(self.chapters):
                ch.index = i

    def _update_toc_indices(self):
        """Update TOC entries to reference their chapter index."""
        for i, entry in enumerate(self._toc_entries):
            entry['chapter_index'] = -1
            for ch in self.chapters:
                if ch.title == entry['title']:
                    entry['chapter_index'] = ch.index
                    break


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("MOBI Ebook Parser & Analyzer")
        print()
        print("Usage: python mobi_parser.py <file.mobi> [options]")
        print()
        print("Options:")
        print("  --json [FILE]   Export book data as JSON (optional output file)")
        print("  --toc            Print table of contents")
        print("  --chapter N      Print content of chapter N")
        print("  --text           Print full text")
        print("  --meta           Print metadata")
        print("  --summary        Print chapter summary stats")
        print("  --chapter-titles Print chapter titles with types and word counts")
        print("  --keep-temp      Keep temporary files (don't cleanup)")
        sys.exit(1)

    filepath = sys.argv[1]

    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    cleanup = '--keep-temp' not in sys.argv

    try:
        # Check for calibre
        if not shutil.which('ebook-convert'):
            print("Error: 'ebook-convert' not found. Please install calibre:")
            print("  brew install --cask calibre")
            sys.exit(1)

        parser = MOBIParser(filepath)
        parser.parse(cleanup=cleanup)
    except Exception as e:
        print(f"Error parsing MOBI file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if '--json' in sys.argv:
        idx = sys.argv.index('--json')
        outpath = sys.argv[idx + 1] if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith('--') else None
        if outpath:
            parser.to_json(outpath)
            print(f"JSON written to {outpath}")
        else:
            print(parser.to_json())
    elif '--toc' in sys.argv:
        print(f"\n{'='*70}")
        print(f"目录: {parser.metadata.title or parser.metadata.full_title}")
        print(f"{'='*70}\n")
        for entry in parser.get_toc():
            indent = '  ' * max(0, entry.get('level', 0))
            ci = entry.get('chapter_index', '?')
            print(f"{indent} [{ci}] {entry['title']}")
    elif '--chapter-titles' in sys.argv:
        meta = parser.get_metadata()
        print(f"\n{'='*70}")
        print(f"{meta.title or meta.full_title}")
        print(f"作者: {meta.author or '未知'}")
        print(f"{'='*70}\n")
        for ch in parser.get_chapters():
            type_tag = f"[{ch.chapter_type}]"
            print(f"  [{ch.index:3d}] {type_tag:20s} {ch.title:40s} {ch.char_count:>6,d} 字")
        total = sum(c.word_count for c in parser.get_chapters())
        print(f"\n  总计: {len(parser.get_chapters())} 章节, {total:,} 字")
    elif '--chapter' in sys.argv:
        idx = sys.argv.index('--chapter')
        if idx + 1 < len(sys.argv):
            n = int(sys.argv[idx + 1])
            ch = parser.get_chapter(n)
            if ch:
                print(f"\n{'='*70}")
                print(f"[{ch.index}] {ch.title} ({ch.chapter_type}, {ch.word_count} words)")
                print(f"{'='*70}\n")
                print(ch.content[:5000])
                if len(ch.content) > 5000:
                    print(f"\n... ({len(ch.content) - 5000} more characters)")
            else:
                print(f"Chapter {n} not found. Total chapters: {len(parser.get_chapters())}")
    elif '--text' in sys.argv:
        print(parser.get_full_text())
    elif '--meta' in sys.argv:
        meta = parser.get_metadata()
        print(f"Title:       {meta.title}")
        print(f"Full Title:  {meta.full_title}")
        print(f"Author:      {meta.author}")
        print(f"Translator:  {meta.translator}")
        print(f"Publisher:   {meta.publisher}")
        print(f"ISBN:        {meta.isbn}")
        print(f"ASIN:        {meta.asin}")
        print(f"Publish Date:{meta.publish_date}")
        print(f"Language:    {meta.language}")
        print(f"Description: {meta.description[:200] if meta.description else 'N/A'}...")
    elif '--summary' in sys.argv:
        meta = parser.get_metadata()
        print(f"\n{'='*70}")
        print(f"书名: {meta.title or meta.full_title}")
        print(f"作者: {meta.author or '未知'}")
        if meta.translator:
            print(f"译者: {meta.translator}")
        if meta.isbn:
            print(f"ISBN: {meta.isbn}")
        if meta.publish_date:
            print(f"出版时间: {meta.publish_date}")
        print(f"{'='*70}\n")
        print(f"总章节数: {len(parser.get_chapters())}")
        total_words = sum(c.word_count for c in parser.get_chapters())
        total_chars = sum(c.char_count for c in parser.get_chapters())
        print(f"总字数:   {total_chars:,} 字符 / ~{total_words:,} 词")
        main_chapters = parser.get_main_chapters()
        print(f"正文章节: {len(main_chapters)}")
        print(f"\n章节明细:")
        print(f"{'-'*70}")
        for ch in parser.get_chapters():
            bar_len = min(ch.char_count // 2000 + 1, 25)
            bar = '█' * bar_len
            type_tag = f"[{ch.chapter_type}]"
            print(f"  [{ch.index:3d}] {type_tag:18s} {ch.title:42s} {ch.char_count:>6,d}字 {bar}")
        print(f"{'-'*70}")
    else:
        # Default: print summary
        meta = parser.get_metadata()
        print(f"\n书名: {meta.title or meta.full_title}")
        print(f"作者: {meta.author or '未知'}")
        print(f"章节: {len(parser.get_chapters())}")
        total_chars = sum(c.char_count for c in parser.get_chapters())
        print(f"总字数: {total_chars:,} 字")
        print("\n使用 --help 查看更多选项")


if __name__ == '__main__':
    main()
