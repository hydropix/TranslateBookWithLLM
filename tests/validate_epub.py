#!/usr/bin/env python3
"""
EPUB Structure Validator

Validates EPUB files for structure compliance without requiring epubcheck.
Checks critical EPUB 2.0/3.0 requirements.

Usage:
    python validate_epub.py path/to/file.epub
    python validate_epub.py tests/fixtures/  # Validate all EPUBs in directory
"""

import os
import sys
import zipfile
from lxml import etree
import argparse


class EPUBValidator:
    """Validates EPUB file structure and compliance."""

    def __init__(self, epub_path):
        self.epub_path = epub_path
        self.errors = []
        self.warnings = []
        self.info = []

    def validate(self):
        """Run all validation checks."""
        if not os.path.exists(self.epub_path):
            self.errors.append(f"File not found: {self.epub_path}")
            return False

        try:
            # Check 1: Valid ZIP file
            if not self._check_zip_structure():
                return False

            # Check 2: Mimetype file
            self._check_mimetype()

            # Check 3: Container.xml
            self._check_container_xml()

            # Check 4: OPF (Package Document)
            self._check_opf()

            # Check 5: NCX (for EPUB 2.0)
            self._check_ncx()

            # Check 6: Content files
            self._check_content_files()

            return len(self.errors) == 0

        except Exception as e:
            self.errors.append(f"Validation error: {str(e)}")
            return False

    def _check_zip_structure(self):
        """Verify the file is a valid ZIP archive."""
        try:
            with zipfile.ZipFile(self.epub_path, 'r') as z:
                # Check for required files
                files = z.namelist()
                self.info.append(f"ZIP contains {len(files)} files")

                if 'mimetype' not in files:
                    self.errors.append("Missing required file: mimetype")
                    return False

                if 'META-INF/container.xml' not in files:
                    self.errors.append("Missing required file: META-INF/container.xml")
                    return False

            return True
        except zipfile.BadZipFile:
            self.errors.append("File is not a valid ZIP archive")
            return False

    def _check_mimetype(self):
        """Check mimetype file is first and uncompressed."""
        with zipfile.ZipFile(self.epub_path, 'r') as z:
            # Check position (should be first)
            if z.namelist()[0] != 'mimetype':
                self.errors.append("ERROR: mimetype must be the first file in the ZIP")
            else:
                self.info.append("PASS: mimetype is first file")

            # Check compression (should be STORED/uncompressed)
            info = z.getinfo('mimetype')
            if info.compress_type != zipfile.ZIP_STORED:
                self.errors.append("ERROR: mimetype must be uncompressed (ZIP_STORED)")
            else:
                self.info.append("PASS: mimetype is uncompressed")

            # Check content
            content = z.read('mimetype').decode('utf-8')
            if content.strip() != 'application/epub+zip':
                self.errors.append(f"ERROR: mimetype content invalid: {content}")
            else:
                self.info.append("PASS: mimetype content is correct")

    def _check_container_xml(self):
        """Verify META-INF/container.xml structure."""
        with zipfile.ZipFile(self.epub_path, 'r') as z:
            try:
                content = z.read('META-INF/container.xml')
                tree = etree.fromstring(content)

                # Check namespace
                ns = {'container': 'urn:oasis:names:tc:opendocument:xmlns:container'}

                # Find rootfiles
                rootfiles = tree.xpath('//container:rootfiles/container:rootfile', namespaces=ns)
                if not rootfiles:
                    self.errors.append("ERROR: No rootfile found in container.xml")
                else:
                    # Get OPF path
                    opf_path = rootfiles[0].get('full-path')
                    if opf_path:
                        self.info.append(f"PASS: OPF path: {opf_path}")
                        # Check if OPF exists
                        if opf_path not in z.namelist():
                            self.errors.append(f"ERROR: OPF file not found: {opf_path}")
                    else:
                        self.errors.append("ERROR: No full-path in rootfile")

            except etree.XMLSyntaxError as e:
                self.errors.append(f"ERROR: Invalid XML in container.xml: {e}")

    def _check_opf(self):
        """Verify OPF (Package Document) structure."""
        with zipfile.ZipFile(self.epub_path, 'r') as z:
            # Find OPF file
            opf_path = None
            for name in z.namelist():
                if name.endswith('.opf'):
                    opf_path = name
                    break

            if not opf_path:
                self.errors.append("ERROR: No OPF file found")
                return

            try:
                content = z.read(opf_path)
                tree = etree.fromstring(content)

                # Check package version
                version = tree.get('version')
                if version:
                    self.info.append(f"PASS: EPUB version: {version}")
                else:
                    self.warnings.append("WARNING: No version attribute in package element")

                # Namespaces
                ns = {
                    'opf': 'http://www.idpf.org/2007/opf',
                    'dc': 'http://purl.org/dc/elements/1.1/'
                }

                # Check metadata
                metadata = tree.xpath('//opf:metadata', namespaces=ns)
                if not metadata:
                    self.errors.append("ERROR: No metadata element in OPF")
                else:
                    # Check required DC elements
                    title = tree.xpath('//dc:title', namespaces=ns)
                    if not title:
                        self.errors.append("ERROR: Missing dc:title")
                    else:
                        self.info.append(f"PASS: Title: {title[0].text}")

                    lang = tree.xpath('//dc:language', namespaces=ns)
                    if not lang:
                        self.errors.append("ERROR: Missing dc:language")
                    else:
                        self.info.append(f"PASS: Language: {lang[0].text}")

                    identifier = tree.xpath('//dc:identifier', namespaces=ns)
                    if not identifier:
                        self.errors.append("ERROR: Missing dc:identifier")
                    else:
                        self.info.append(f"PASS: Identifier: {identifier[0].text}")

                # Check manifest
                manifest = tree.xpath('//opf:manifest', namespaces=ns)
                if not manifest:
                    self.errors.append("ERROR: No manifest element in OPF")
                else:
                    items = tree.xpath('//opf:manifest/opf:item', namespaces=ns)
                    self.info.append(f"PASS: Manifest contains {len(items)} items")

                    # Check each item exists
                    opf_dir = os.path.dirname(opf_path)
                    for item in items:
                        href = item.get('href')
                        if href:
                            full_path = os.path.join(opf_dir, href).replace('\\', '/')
                            # Normalize path
                            if opf_dir:
                                full_path = f"{opf_dir}/{href}"
                            else:
                                full_path = href

                            if full_path not in z.namelist():
                                self.warnings.append(f"WARNING: Manifest item not found: {full_path}")

                # Check spine
                spine = tree.xpath('//opf:spine', namespaces=ns)
                if not spine:
                    self.errors.append("ERROR: No spine element in OPF")
                else:
                    itemrefs = tree.xpath('//opf:spine/opf:itemref', namespaces=ns)
                    self.info.append(f"PASS: Spine contains {len(itemrefs)} items")

                    if len(itemrefs) == 0:
                        self.errors.append("ERROR: Spine is empty")

            except etree.XMLSyntaxError as e:
                self.errors.append(f"ERROR: Invalid XML in OPF: {e}")

    def _check_ncx(self):
        """Check NCX navigation document (EPUB 2.0)."""
        with zipfile.ZipFile(self.epub_path, 'r') as z:
            # Find NCX file
            ncx_path = None
            for name in z.namelist():
                if name.endswith('.ncx'):
                    ncx_path = name
                    break

            if not ncx_path:
                self.warnings.append("WARNING: No NCX file found (optional for EPUB 3.0)")
                return

            try:
                content = z.read(ncx_path)
                tree = etree.fromstring(content)

                ns = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}

                # Check navMap
                navmap = tree.xpath('//ncx:navMap', namespaces=ns)
                if navmap:
                    navpoints = tree.xpath('//ncx:navMap/ncx:navPoint', namespaces=ns)
                    self.info.append(f"PASS: NCX contains {len(navpoints)} navigation points")
                else:
                    self.warnings.append("WARNING: No navMap in NCX")

            except etree.XMLSyntaxError as e:
                self.errors.append(f"ERROR: Invalid XML in NCX: {e}")

    def _check_content_files(self):
        """Verify content files (XHTML) are well-formed."""
        with zipfile.ZipFile(self.epub_path, 'r') as z:
            xhtml_files = [f for f in z.namelist() if f.endswith('.xhtml') or f.endswith('.html')]

            self.info.append(f"PASS: Found {len(xhtml_files)} content files")

            for xhtml_file in xhtml_files:
                try:
                    content = z.read(xhtml_file)
                    # Try to parse as XML
                    etree.fromstring(content)
                except etree.XMLSyntaxError as e:
                    self.warnings.append(f"WARNING: Malformed XML in {xhtml_file}: {str(e)[:100]}")

    def report(self):
        """Generate validation report."""
        lines = [
            f"\nEPUB Validation Report: {os.path.basename(self.epub_path)}",
            "=" * 60
        ]

        # Errors
        if self.errors:
            lines.append(f"\nERRORS ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  - {error}")
        else:
            lines.append("\nNo errors found!")

        # Warnings
        if self.warnings:
            lines.append(f"\nWARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        # Info (detailed)
        if self.info:
            lines.append(f"\nDETAILS ({len(self.info)}):")
            for info in self.info:
                lines.append(f"  - {info}")

        # Summary
        lines.append("\n" + "=" * 60)
        if not self.errors:
            lines.append("RESULT: VALID EPUB")
        else:
            lines.append(f"RESULT: INVALID EPUB ({len(self.errors)} errors)")

        return "\n".join(lines)


def validate_epub(path):
    """Validate a single EPUB file or all EPUBs in a directory."""
    if os.path.isdir(path):
        # Validate all EPUBs in directory
        epub_files = [f for f in os.listdir(path) if f.endswith('.epub')]
        if not epub_files:
            print(f"No EPUB files found in {path}")
            return False

        all_valid = True
        for epub_file in epub_files:
            epub_path = os.path.join(path, epub_file)
            validator = EPUBValidator(epub_path)
            valid = validator.validate()
            print(validator.report())
            if not valid:
                all_valid = False
            print()

        return all_valid

    else:
        # Validate single file
        validator = EPUBValidator(path)
        valid = validator.validate()
        print(validator.report())
        return valid


def main():
    parser = argparse.ArgumentParser(description="Validate EPUB file structure")
    parser.add_argument("path", help="Path to EPUB file or directory containing EPUBs")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all details")

    args = parser.parse_args()

    valid = validate_epub(args.path)
    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
