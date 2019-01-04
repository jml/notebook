"""Markdown extension for sidenotes.

Subverts the "footnotes" syntax as used by the footnotes extension of markdown
to implement "sidenotes". Sidenotes are notes that appear in the right-hand
margin of a document, and are documented at
<https://edwardtufte.github.io/tufte-css/#sidenotes>.

Sidenotes are expected to have only inline text, i.e. no block elements. This
restriction comes from Tufte CSS, and is (probably) not enforced in this code.

Do not use this extension together with the footnotes extension, as they rely
on the same syntax.
"""

from __future__ import unicode_literals

import re

import attr

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.inlinepatterns import Pattern
from markdown import util


@attr.s(frozen=True)
class Footnote(object):
    """A single footnote."""
    id = attr.ib()
    label = attr.ib()
    text = attr.ib()

    def get_html_id(self):
        return 'sn-' + str(self.id)


@attr.s
class Footnotes(object):
    """Registry of footnotes in a document."""
    _footnotes = attr.ib(default=attr.Factory(dict))
    _counter = attr.ib(default=0)

    def add(self, label, text):
        self._counter += 1
        footnote = Footnote(self._counter, label, text)
        self._footnotes[label] = footnote
        return footnote

    def get_by_label(self, label):
        return self._footnotes.get(label, None)


class SidenoteExtension(Extension):
    """Sidenotes for Tufte CSS."""

    def __init__(self, *args, **kwargs):
        super(SidenoteExtension, self).__init__(*args, **kwargs)
        self._footnotes = Footnotes()

    def extendMarkdown(self, md, md_globals):
        """Subvert markdown syntax so footnotes become sidenotes."""
        md.registerExtension(self)
        # Insert a preprocessor before ReferencePreprocessor
        md.preprocessors.add(
            'sidenote', FootnotePreprocessor(self._footnotes), "<reference"
        )
        # Insert an inline pattern before ImageReferencePattern
        FOOTNOTE_RE = r'\[\^([^\]]*)\]'  # blah blah [^1] blah
        md.inlinePatterns.add(
            'sidenote', FootnotePattern(
                FOOTNOTE_RE, self._footnotes, md.parser), "<reference"
        )


DEF_RE = re.compile(r'[ ]{0,3}\[\^([^\]]*)\]:\s*(.*)')


class FootnotePreprocessor(Preprocessor):
    """Find all footnote definitions and store for later use.

    This was copied from the "footnotes" extension of markdown.
    """

    def __init__(self, footnotes):
        self.footnotes = footnotes

    def run(self, lines):
        """
        Loop through lines and find, set, and remove footnote definitions.

        Keywords:

        * lines: A list of lines of text

        Return: A list of lines of text with footnote definitions removed.

        """
        newlines = []
        i = 0
        while True:
            m = DEF_RE.match(lines[i])
            if m:
                fn, _i = detect_tabbed(lines[i+1:])
                fn.insert(0, m.group(2))
                i += _i-1  # skip past footnote
                footnote = "\n".join(fn)
                self.footnotes.add(m.group(1), footnote.rstrip())
                # Preserve a line for each block to prevent raw HTML indexing
                # issue.
                # https://github.com/Python-Markdown/markdown/issues/584
                num_blocks = (len(footnote.split('\n\n')) * 2)
                newlines.extend([''] * (num_blocks))
            else:
                newlines.append(lines[i])
            if len(lines) > i+1:
                i += 1
            else:
                break
        return newlines


TABBED_RE = re.compile(r'((\t)|(    ))(.*)')


def detect_tabbed(lines):
    """Find indented text and remove indent before further proccesing.

    This was copied from the "footnotes" extension of markdown.

    Keyword arguments:

    * lines: an array of strings

    Returns: a list of post processed items and the index of last line.
    """
    items = []
    blank_line = False  # have we encountered a blank line yet?
    i = 0  # to keep track of where we are

    def detab(line):
        match = TABBED_RE.match(line)
        if match:
            return match.group(4)

    for line in lines:
        if line.strip():  # Non-blank line
            detabbed_line = detab(line)
            if detabbed_line:
                items.append(detabbed_line)
                i += 1
                continue
            elif not blank_line and not DEF_RE.match(line):
                # not tabbed but still part of first par.
                items.append(line)
                i += 1
                continue
            else:
                return items, i+1

        else:  # Blank line: _maybe_ we are done.
            blank_line = True
            i += 1  # advance

            # Find the next non-blank line
            for j in range(i, len(lines)):
                if lines[j].strip():
                    next_line = lines[j]
                    break
                else:
                    # Include extreaneous padding to prevent raw HTML
                    # parsing issue:
                    # https://github.com/Python-Markdown/markdown/issues/584
                    items.append("")
                    i += 1
            else:
                break  # There is no more text; we are done.

            # Check if the next non-blank line is tabbed
            if detab(next_line):  # Yes, more work to do.
                items.append("")
                continue
            else:
                break  # No, we are done.
    else:
        i += 1

    return items, i


class FootnotePattern(Pattern):
    """InlinePattern for footnote markers in a document's body text."""

    def __init__(self, pattern, footnotes, parser):
        super(FootnotePattern, self).__init__(pattern)
        self.footnotes = footnotes
        self.parser = parser

    def handleMatch(self, m):
        """When we find a footnote marker, replace it with a sidenote node."""
        label = m.group(2)
        footnote = self.footnotes.get_by_label(label)
        if not footnote:
            return
        html_id = footnote.get_html_id()
        return create_sidenote(html_id, footnote.text, self.parser)


def create_sidenote(html_id, text, parser):
    """Create a sidenote element.

    From https://edwardtufte.github.io/tufte-css/#sidenotes::

    Sidenotes consist of two elements: a superscript reference number that
    goes inline with the text, and a sidenote with content. To add the former,
    just put a label and dummy checkbox into the text where you want the
    reference to go, like so:

    <label for="sn-demo"
           class="margin-toggle sidenote-number">
    </label>
    <input type="checkbox"
           id="sn-demo"
           class="margin-toggle"/>

    You must manually assign a reference id to each side or margin note,
    replacing “sn-demo” in the for and the id attribute values with an
    appropriate descriptor. It is useful to use prefixes like sn- for
    sidenotes and mn- for margin notes.

    Immediately adjacent to that sidenote reference in the main text goes the
    sidenote content itself, in a span with class sidenote. This tag is also
    inserted directly in the middle of the body text, but is either pushed
    into the margin or hidden by default. Make sure to position your sidenotes
    correctly by keeping the sidenote-number label close to the sidenote
    itself.
    """
    root = util.etree.Element('span')
    label = util.etree.SubElement(root, 'label')
    label.set('for', html_id)
    label.set('class', 'margin-toggle sidenote-number')
    checkbox = util.etree.SubElement(root, 'input')
    checkbox.set('type', 'checkbox')
    checkbox.set('id', html_id)
    checkbox.set('class', 'margin-toggle')
    span = util.etree.SubElement(root, 'span')
    span.set('class', 'sidenote')
    span.text = text
    return root
