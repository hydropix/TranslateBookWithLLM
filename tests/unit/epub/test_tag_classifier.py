"""Unit tests for TagClassifier."""
import pytest
from src.core.epub.tag_classifier import TagClassifier


class TestTagClassifier:
    """Test TagClassifier functionality."""

    @pytest.fixture
    def classifier(self):
        """Create a TagClassifier instance."""
        return TagClassifier()

    # Test block opening tag detection
    def test_is_block_opening_tag_paragraph(self, classifier):
        """Test detection of paragraph opening tag."""
        assert classifier.is_block_opening_tag("<p>")
        assert classifier.is_block_opening_tag("<p class='test'>")
        assert classifier.is_block_opening_tag("<P>")

    def test_is_block_opening_tag_div(self, classifier):
        """Test detection of div opening tag."""
        assert classifier.is_block_opening_tag("<div>")
        assert classifier.is_block_opening_tag("<div id='content'>")
        assert classifier.is_block_opening_tag("<DIV>")

    def test_is_block_opening_tag_headings(self, classifier):
        """Test detection of heading opening tags."""
        for level in range(1, 7):
            assert classifier.is_block_opening_tag(f"<h{level}>")
            assert classifier.is_block_opening_tag(f"<h{level} class='title'>")

    def test_is_block_opening_tag_other_blocks(self, classifier):
        """Test detection of other block opening tags."""
        assert classifier.is_block_opening_tag("<blockquote>")
        assert classifier.is_block_opening_tag("<section>")
        assert classifier.is_block_opening_tag("<article>")
        assert classifier.is_block_opening_tag("<li>")
        assert classifier.is_block_opening_tag("<tr>")
        assert classifier.is_block_opening_tag("<td>")
        assert classifier.is_block_opening_tag("<th>")

    def test_is_block_opening_tag_inline_tags(self, classifier):
        """Test that inline tags are not detected as block tags."""
        assert not classifier.is_block_opening_tag("<span>")
        assert not classifier.is_block_opening_tag("<a>")
        assert not classifier.is_block_opening_tag("<em>")
        assert not classifier.is_block_opening_tag("<strong>")
        assert not classifier.is_block_opening_tag("<b>")
        assert not classifier.is_block_opening_tag("<i>")

    # Test block closing tag detection
    def test_is_block_closing_tag_paragraph(self, classifier):
        """Test detection of paragraph closing tag."""
        assert classifier.is_block_closing_tag("</p>")
        assert classifier.is_block_closing_tag("</P>")

    def test_is_block_closing_tag_div(self, classifier):
        """Test detection of div closing tag."""
        assert classifier.is_block_closing_tag("</div>")
        assert classifier.is_block_closing_tag("</DIV>")

    def test_is_block_closing_tag_headings(self, classifier):
        """Test detection of heading closing tags."""
        for level in range(1, 7):
            assert classifier.is_block_closing_tag(f"</h{level}>")

    def test_is_block_closing_tag_other_blocks(self, classifier):
        """Test detection of other block closing tags."""
        assert classifier.is_block_closing_tag("</blockquote>")
        assert classifier.is_block_closing_tag("</section>")
        assert classifier.is_block_closing_tag("</article>")
        assert classifier.is_block_closing_tag("</li>")
        assert classifier.is_block_closing_tag("</tr>")
        assert classifier.is_block_closing_tag("</td>")
        assert classifier.is_block_closing_tag("</th>")

    def test_is_block_closing_tag_inline_tags(self, classifier):
        """Test that inline tags are not detected as block tags."""
        assert not classifier.is_block_closing_tag("</span>")
        assert not classifier.is_block_closing_tag("</a>")
        assert not classifier.is_block_closing_tag("</em>")
        assert not classifier.is_block_closing_tag("</strong>")
        assert not classifier.is_block_closing_tag("</b>")
        assert not classifier.is_block_closing_tag("</i>")

    # Test chapter heading detection
    def test_is_chapter_heading_h1_to_h3(self, classifier):
        """Test detection of chapter headings (h1-h3)."""
        assert classifier.is_chapter_heading("</h1>")
        assert classifier.is_chapter_heading("</h2>")
        assert classifier.is_chapter_heading("</h3>")
        assert classifier.is_chapter_heading("</H1>")
        assert classifier.is_chapter_heading("</H2>")
        assert classifier.is_chapter_heading("</H3>")

    def test_is_chapter_heading_h4_to_h6(self, classifier):
        """Test that h4-h6 are not chapter headings."""
        assert not classifier.is_chapter_heading("</h4>")
        assert not classifier.is_chapter_heading("</h5>")
        assert not classifier.is_chapter_heading("</h6>")

    def test_is_chapter_heading_other_tags(self, classifier):
        """Test that other tags are not chapter headings."""
        assert not classifier.is_chapter_heading("</p>")
        assert not classifier.is_chapter_heading("</div>")
        assert not classifier.is_chapter_heading("</section>")

    # Test split priority
    def test_get_split_priority_chapter_headings(self, classifier):
        """Test priority 1 for chapter headings."""
        assert classifier.get_split_priority("</h1>") == 1
        assert classifier.get_split_priority("</h2>") == 1
        assert classifier.get_split_priority("</h3>") == 1

    def test_get_split_priority_major_sections(self, classifier):
        """Test priority 2 for major sections."""
        assert classifier.get_split_priority("</h4>") == 2
        assert classifier.get_split_priority("</h5>") == 2
        assert classifier.get_split_priority("</h6>") == 2
        assert classifier.get_split_priority("</section>") == 2
        assert classifier.get_split_priority("</article>") == 2

    def test_get_split_priority_paragraphs(self, classifier):
        """Test priority 3 for paragraphs."""
        assert classifier.get_split_priority("</p>") == 3
        assert classifier.get_split_priority("</div>") == 3
        assert classifier.get_split_priority("</blockquote>") == 3

    def test_get_split_priority_other_blocks(self, classifier):
        """Test priority 4 for other block elements."""
        assert classifier.get_split_priority("</li>") == 4
        assert classifier.get_split_priority("</tr>") == 4
        assert classifier.get_split_priority("</td>") == 4
        assert classifier.get_split_priority("</th>") == 4

    def test_get_split_priority_case_insensitive(self, classifier):
        """Test that priority detection is case-insensitive."""
        assert classifier.get_split_priority("</H1>") == 1
        assert classifier.get_split_priority("</P>") == 3
        assert classifier.get_split_priority("</DIV>") == 3
