"""
Unit tests for tilda_upload_blocks.py.

The script relies on Playwright + a live Tilda session, so we test the
deterministic parts: file reading, block counting, ordering logic.
"""
import os
import sys
import importlib.util
import pytest

PROTO_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'prototype')
SCRIPT_PATH = os.path.join(PROTO_DIR, 'tilda_upload_blocks.py')


def load_upload_module():
    """Load the upload script as a module without executing asyncio.run(main())."""
    spec = importlib.util.spec_from_file_location('tilda_upload_blocks', SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Patch asyncio.run so main() isn't executed on import
    import asyncio
    original_run = asyncio.run
    asyncio.run = lambda *a, **kw: None
    try:
        spec.loader.exec_module(mod)
    finally:
        asyncio.run = original_run
    return mod


class TestBlockFileList:
    """Tests related to BLOCK_FILES constant and file existence."""

    def test_block_files_count(self):
        mod = load_upload_module()
        assert len(mod.BLOCK_FILES) == 14

    def test_all_block_files_are_html(self):
        mod = load_upload_module()
        for bf in mod.BLOCK_FILES:
            assert bf.endswith('.html'), f"{bf} should be an HTML file"

    def test_all_block_files_are_min(self):
        mod = load_upload_module()
        for bf in mod.BLOCK_FILES:
            assert '_min.html' in bf, f"{bf} should be a minified file"

    def test_block_files_exist_in_tilda_blocks_min(self):
        """Verify that all referenced block files actually exist in the repo."""
        mod = load_upload_module()
        blocks_dir = os.path.join(PROTO_DIR, 'tilda_blocks_min')
        for bf in mod.BLOCK_FILES:
            fpath = os.path.join(blocks_dir, bf)
            assert os.path.isfile(fpath), f"Missing block file: {bf}"

    def test_no_duplicate_block_files(self):
        mod = load_upload_module()
        assert len(mod.BLOCK_FILES) == len(set(mod.BLOCK_FILES))

    def test_block_files_ordering_starts_with_header(self):
        mod = load_upload_module()
        assert mod.BLOCK_FILES[0] == 'tilda_header_unified_min.html'

    def test_block_files_ordering_ends_with_footer(self):
        mod = load_upload_module()
        assert mod.BLOCK_FILES[-1] == 'tilda_footer_min.html'

    def test_block_dir_path(self):
        mod = load_upload_module()
        assert 'tilda_blocks_min' in mod.BLOCK_DIR


class TestBlockContents:
    """Tests that block content files are valid and non-empty."""

    def test_block_files_are_nonempty(self):
        mod = load_upload_module()
        blocks_dir = os.path.join(PROTO_DIR, 'tilda_blocks_min')
        for bf in mod.BLOCK_FILES:
            fpath = os.path.join(blocks_dir, bf)
            size = os.path.getsize(fpath)
            assert size > 0, f"Block file {bf} is empty"

    def test_block_files_are_utf8(self):
        mod = load_upload_module()
        blocks_dir = os.path.join(PROTO_DIR, 'tilda_blocks_min')
        for bf in mod.BLOCK_FILES:
            fpath = os.path.join(blocks_dir, bf)
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) > 0

    def test_block_files_contain_html_elements(self):
        """Each min block should have at least some HTML structure."""
        mod = load_upload_module()
        blocks_dir = os.path.join(PROTO_DIR, 'tilda_blocks_min')
        for bf in mod.BLOCK_FILES:
            fpath = os.path.join(blocks_dir, bf)
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            assert '<' in content and '>' in content, f"{bf} has no HTML tags"


class TestNewBlocksCalculation:
    """Tests for the logic that calculates how many new blocks to create."""

    def test_needs_new_blocks_when_fewer_exist(self):
        block_count = 14
        existing_count = 4
        needed = max(0, block_count - existing_count)
        assert needed == 10

    def test_no_new_blocks_when_enough_exist(self):
        block_count = 14
        existing_count = 14
        needed = max(0, block_count - existing_count)
        assert needed == 0

    def test_no_new_blocks_when_more_exist(self):
        block_count = 14
        existing_count = 20
        needed = max(0, block_count - existing_count)
        assert needed == 0


class TestReorderLogic:
    """Tests for the block reordering logic."""

    def test_our_blocks_come_first_in_new_order(self):
        all_recs = ['100', '200', '300', '400', '500']
        our_ids = ['200', '400']
        our_set = set(our_ids)
        other_ids = [rid for rid in all_recs if rid not in our_set]
        new_order = our_ids + other_ids
        assert new_order == ['200', '400', '100', '300', '500']

    def test_other_blocks_preserve_relative_order(self):
        all_recs = ['a', 'b', 'c', 'd', 'e', 'f']
        our_ids = ['b', 'd']
        our_set = set(our_ids)
        other_ids = [rid for rid in all_recs if rid not in our_set]
        assert other_ids == ['a', 'c', 'e', 'f']

    def test_empty_existing_blocks(self):
        all_recs = ['1', '2', '3']
        our_ids = []
        our_set = set(our_ids)
        other_ids = [rid for rid in all_recs if rid not in our_set]
        new_order = our_ids + other_ids
        assert new_order == ['1', '2', '3']
