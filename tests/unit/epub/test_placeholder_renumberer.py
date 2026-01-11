"""
Unit tests for PlaceholderRenumberer.

Tests the placeholder renumbering logic that converts global placeholders
to local indices within chunks.
"""
import unittest
from src.core.epub.placeholder_renumberer import PlaceholderRenumberer


class TestPlaceholderRenumberer(unittest.TestCase):
    """Test PlaceholderRenumberer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.renumberer = PlaceholderRenumberer()

    def test_basic_renumbering(self):
        """Test basic placeholder renumbering from global to local indices."""
        text = "[id5]Hello[id6]world[id7]"
        global_tag_map = {
            "[id5]": "<p>",
            "[id6]": "<b>",
            "[id7]": "</b></p>"
        }
        global_offset = 0

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        self.assertEqual(result['text'], "[id0]Hello[id1]world[id2]")
        self.assertEqual(result['local_tag_map'], {
            "[id0]": "<p>",
            "[id1]": "<b>",
            "[id2]": "</b></p>"
        })
        self.assertEqual(result['global_offset'], 0)
        self.assertEqual(result['global_indices'], [5, 6, 7])

    def test_renumbering_with_offset(self):
        """Test renumbering with non-zero global offset."""
        text = "[id10]Test[id11]"
        global_tag_map = {
            "[id10]": "<span>",
            "[id11]": "</span>"
        }
        global_offset = 5

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        self.assertEqual(result['text'], "[id0]Test[id1]")
        self.assertEqual(result['local_tag_map'], {
            "[id0]": "<span>",
            "[id1]": "</span>"
        })
        self.assertEqual(result['global_offset'], 5)
        self.assertEqual(result['global_indices'], [10, 11])

    def test_duplicate_placeholders(self):
        """Test that duplicate global placeholders get unique local indices."""
        text = "[id5]Start[id5]End[id5]"
        global_tag_map = {
            "[id5]": "<br/>"
        }
        global_offset = 0

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        # Each occurrence should get a unique local index
        self.assertEqual(result['text'], "[id0]Start[id1]End[id2]")
        self.assertEqual(result['local_tag_map'], {
            "[id0]": "<br/>",
            "[id1]": "<br/>",
            "[id2]": "<br/>"
        })
        self.assertEqual(result['global_indices'], [5, 5, 5])

    def test_empty_text(self):
        """Test handling of empty text."""
        text = ""
        global_tag_map = {}
        global_offset = 0

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        self.assertEqual(result['text'], "")
        self.assertEqual(result['local_tag_map'], {})
        self.assertEqual(result['global_indices'], [])

    def test_text_without_placeholders(self):
        """Test text without any placeholders."""
        text = "Hello world"
        global_tag_map = {}
        global_offset = 0

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        self.assertEqual(result['text'], "Hello world")
        self.assertEqual(result['local_tag_map'], {})
        self.assertEqual(result['global_indices'], [])

    def test_consecutive_placeholders(self):
        """Test consecutive placeholders without text between them."""
        text = "[id1][id2][id3]"
        global_tag_map = {
            "[id1]": "<div>",
            "[id2]": "<p>",
            "[id3]": "</p></div>"
        }
        global_offset = 0

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        self.assertEqual(result['text'], "[id0][id1][id2]")
        self.assertEqual(result['local_tag_map'], {
            "[id0]": "<div>",
            "[id1]": "<p>",
            "[id2]": "</p></div>"
        })
        self.assertEqual(result['global_indices'], [1, 2, 3])

    def test_large_global_indices(self):
        """Test handling of large global indices."""
        text = "[id999]Content[id1000]"
        global_tag_map = {
            "[id999]": "<section>",
            "[id1000]": "</section>"
        }
        global_offset = 500

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        self.assertEqual(result['text'], "[id0]Content[id1]")
        self.assertEqual(result['local_tag_map'], {
            "[id0]": "<section>",
            "[id1]": "</section>"
        })
        self.assertEqual(result['global_offset'], 500)
        self.assertEqual(result['global_indices'], [999, 1000])

    def test_missing_tag_in_map(self):
        """Test handling of placeholders not present in global tag map."""
        text = "[id5]Test[id6]"
        global_tag_map = {
            "[id5]": "<p>"
            # [id6] is missing from map
        }
        global_offset = 0

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        self.assertEqual(result['text'], "[id0]Test[id1]")
        self.assertEqual(result['local_tag_map'], {
            "[id0]": "<p>",
            "[id1]": ""  # Should default to empty string
        })
        self.assertEqual(result['global_indices'], [5, 6])

    def test_complex_html_structure(self):
        """Test with complex HTML structure and multiple placeholder types."""
        text = "[id0]<h1>Chapter 1</h1>[id1][id2]Some text[id3][id4]More text[id5]"
        global_tag_map = {
            "[id0]": "<div>",
            "[id1]": "</div>",
            "[id2]": "<p>",
            "[id3]": "</p>",
            "[id4]": "<p>",
            "[id5]": "</p>"
        }
        global_offset = 10

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        expected_text = "[id0]<h1>Chapter 1</h1>[id1][id2]Some text[id3][id4]More text[id5]"
        # Replace global indices with local (0-5)
        expected_text = "[id0]<h1>Chapter 1</h1>[id1][id2]Some text[id3][id4]More text[id5]"

        self.assertEqual(result['text'], expected_text)
        self.assertEqual(len(result['local_tag_map']), 6)
        self.assertEqual(result['global_indices'], [0, 1, 2, 3, 4, 5])

    def test_placeholder_order_preservation(self):
        """Test that placeholder order is preserved during renumbering."""
        text = "[id10]A[id20]B[id15]C[id5]"
        global_tag_map = {
            "[id10]": "<tag1>",
            "[id20]": "<tag2>",
            "[id15]": "<tag3>",
            "[id5]": "<tag4>"
        }
        global_offset = 0

        result = self.renumberer.create_chunk_with_local_placeholders(
            text, global_tag_map, global_offset
        )

        # Local indices should follow the order of appearance, not global indices
        self.assertEqual(result['text'], "[id0]A[id1]B[id2]C[id3]")
        self.assertEqual(result['global_indices'], [10, 20, 15, 5])

        # Verify the mapping follows the correct order
        self.assertEqual(result['local_tag_map']["[id0]"], "<tag1>")
        self.assertEqual(result['local_tag_map']["[id1]"], "<tag2>")
        self.assertEqual(result['local_tag_map']["[id2]"], "<tag3>")
        self.assertEqual(result['local_tag_map']["[id3]"], "<tag4>")


if __name__ == '__main__':
    unittest.main()
