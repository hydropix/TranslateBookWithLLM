"""
Test replace_body_content to find the bug
"""
from lxml import etree


def replace_body_content_current(body_element: etree._Element, new_html: str) -> None:
    """Current implementation from body_serializer.py"""
    # Clear the body
    body_element.text = None
    for child in list(body_element):
        body_element.remove(child)

    # Parse the new content
    # Wrap in a temp element to handle multiple root elements
    wrapped = f"<temp xmlns='http://www.w3.org/1999/xhtml'>{new_html}</temp>"
    parser = etree.XMLParser(recover=True, encoding='utf-8')

    try:
        temp = etree.fromstring(wrapped.encode('utf-8'), parser)
    except etree.XMLSyntaxError:
        # Fallback: try without namespace
        wrapped = f"<temp>{new_html}</temp>"
        temp = etree.fromstring(wrapped.encode('utf-8'), parser)

    # Copy content into body
    body_element.text = temp.text
    for child in temp:
        body_element.append(child)


def test_replace_body():
    """Test if replace_body_content correctly handles multiple paragraphs"""

    # Create a simple XHTML document
    xhtml = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Test</title></head>
<body>
<p>Original paragraph 1</p>
<p>Original paragraph 2</p>
</body>
</html>"""

    parser = etree.XMLParser(encoding='utf-8')
    doc_root = etree.fromstring(xhtml.encode('utf-8'), parser)

    # Find body
    body = doc_root.find('.//{http://www.w3.org/1999/xhtml}body')

    print("Original body content:")
    print(etree.tostring(body, encoding='unicode', method='xml'))
    print()

    # New translated HTML (3 paragraphs this time)
    new_html = "<p>Translated paragraph 1</p><p>Translated paragraph 2</p><p>Translated paragraph 3</p>"

    print(f"New HTML to insert: {new_html}")
    print()

    # Replace body content
    replace_body_content_current(body, new_html)

    print("Body after replacement:")
    result = etree.tostring(body, encoding='unicode', method='xml')
    print(result)
    print()

    # Check if all 3 paragraphs are present
    paragraphs = body.findall('.//{http://www.w3.org/1999/xhtml}p')
    print(f"Number of <p> elements found: {len(paragraphs)}")
    for i, p in enumerate(paragraphs):
        print(f"  Paragraph {i+1}: {p.text}")
    print()

    # Expected: 3 paragraphs
    if len(paragraphs) == 3:
        print("✓ SUCCESS: All 3 paragraphs present")
        return True
    else:
        print(f"✗ FAILURE: Expected 3 paragraphs, found {len(paragraphs)}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Testing replace_body_content")
    print("=" * 70)
    print()

    success = test_replace_body()

    print("=" * 70)
    if success:
        print("Test passed - no bug found")
        print()
        print("This means the bug must be elsewhere...")
        print("Possible locations:")
        print("- tag_preserver.restore_tags() not restoring all tags?")
        print("- full_translated string is incomplete?")
        print("- final_html is incomplete?")
    else:
        print("Test failed - bug confirmed in replace_body_content!")
