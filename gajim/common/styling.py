# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Union
from typing import Match

import string
import re
from dataclasses import dataclass
from dataclasses import field

from gi.repository import GLib

from gajim.gui.emoji_data import emoji_data

PRE = '`'
STRONG = '*'
STRIKE = '~'
EMPH = '_'

WHITESPACE = set(string.whitespace)
SPAN_DIRS = set([PRE, STRONG, STRIKE, EMPH])
VALID_SPAN_START = WHITESPACE | SPAN_DIRS

PRE_RX = r'(?P<pre>^```.+?(^```$(.|\Z)))'
PRE_NESTED_RX = r'(?P<pre>^```.+?((^```$(.|\Z))|\Z))'
QUOTE_RX = r'(?P<quote>^(?=>).*?(^|\Z)(?!>))'

BLOCK_RX = re.compile(PRE_RX + '|' + QUOTE_RX, re.S | re.M)
BLOCK_NESTED_RX = re.compile(PRE_NESTED_RX + '|' + QUOTE_RX, re.S | re.M)
UNQUOTE_RX = re.compile(r'^> |^>', re.M)

URI_RX = r'((?P<protocol>[\w-]+://?|www[.])[\S()<>]+?(?=[,]?(\s|\Z)+))'
URI_RX = re.compile(URI_RX)

ADDRESS_RX = r'(\b(?P<protocol>(xmpp|mailto)+:)?[\w-]*@(.*?\.)+[\w]+([\?].*?(?=([\s\),]|$)))?)'
ADDRESS_RX = re.compile(ADDRESS_RX)

EMOJI_RX = emoji_data.get_regex()
EMOJI_RX = re.compile(EMOJI_RX)

SD = 0
SD_POS = 1


@dataclass
class StyleObject:
    start: int
    end: int
    text: str


@dataclass
class BaseUri(StyleObject):
    name: str
    start_byte: int
    end_byte: int

    def get_markup_string(self) -> str:
        text = GLib.markup_escape_text(self.text)
        return f'<a href="{text}">{text}</a>'


@dataclass
class Uri(BaseUri):
    name: str = field(default='uri', init=False)


@dataclass
class Address(BaseUri):
    name: str = field(default='address', init=False)


@dataclass
class XMPPAddress(BaseUri):
    name: str = field(default='xmppadr', init=False)


@dataclass
class MailAddress(BaseUri):
    name: str = field(default='mailadr', init=False)


@dataclass
class Emoji(StyleObject):
    name: str = field(default='emoji', init=False)


@dataclass
class Block(StyleObject):

    @classmethod
    def from_match(cls, match: Match[str]) -> Block:
        return cls(start=match.start(),
                   end=match.end(),
                   text=match.group(cls.name))


@dataclass
class PlainBlock(Block):
    name: str = field(default='plain', init=False)
    spans: list[Span] = field(default_factory=list)
    uris: list[BaseUri] = field(default_factory=list)
    emojis: list[Emoji] = field(default_factory=list)


@dataclass
class PreBlock(Block):
    name: str = field(default='pre', init=False)


@dataclass
class QuoteBlock(Block):
    name: str = field(default='quote', init=False)
    blocks: list[Block] = field(default_factory=list)

    def unquote(self) -> str:
        return UNQUOTE_RX.sub('', self.text)


@dataclass
class Span(StyleObject):
    start_byte: int
    end_byte: int
    name: str


@dataclass
class PlainSpan(Span):
    name: str = field(default='plain', init=False)


@dataclass
class StrongSpan(Span):
    name: str = field(default='strong', init=False)


@dataclass
class EmphasisSpan(Span):
    name: str = field(default='emphasis', init=False)


@dataclass
class PreTextSpan(Span):
    name: str = field(default='pre', init=False)


@dataclass
class StrikeSpan(Span):
    name: str = field(default='strike', init=False)


SPAN_CLS_DICT = {
    STRONG: StrongSpan,
    EMPH: EmphasisSpan,
    PRE: PreTextSpan,
    STRIKE: StrikeSpan
}


@dataclass
class ParsingResult:
    text: str
    blocks: list[Block]


def find_byte_index(text: str, index: int):
    byte_index = -1
    for index_, c in enumerate(text):
        byte_index += len(c.encode())
        if index == index_:
            return byte_index

    raise ValueError('index not in string: %s, %s' % (text, index))


def process(text: Union[str, bytes], nested: bool = False) -> ParsingResult:
    if isinstance(text, bytes):
        text = text.decode()

    blocks = _parse_blocks(text, nested)
    for block in blocks:
        if isinstance(block, PlainBlock):
            offset = 0
            offset_bytes = 0
            for line in block.text.splitlines(keepends=True):
                block.spans += _parse_line(line, offset, offset_bytes)
                block.uris += _parse_uris(line, offset, offset_bytes)
                block.emojis += _parse_emojis(line, offset)
                offset += len(line)
                offset_bytes += len(line.encode())

        if isinstance(block, QuoteBlock):
            result = process(block.unquote(), nested=True)
            block.blocks = result.blocks

    return ParsingResult(text, blocks)


def _parse_blocks(text: str, nested: bool) -> list[Block]:
    blocks: list[Block] = []
    text_len = len(text)
    last_end_pos = 0

    rx = BLOCK_NESTED_RX if nested else BLOCK_RX

    for match in rx.finditer(text):
        if match.start() != last_end_pos:
            blocks.append(PlainBlock(
                start=last_end_pos,
                end=match.start(),
                text=text[last_end_pos:match.start()]))

        last_end_pos = match.end()
        group_dict = match.groupdict()

        if group_dict.get('quote') is not None:
            blocks.append(QuoteBlock.from_match(match))

        if group_dict.get('pre') is not None:
            blocks.append(PreBlock.from_match(match))

    if last_end_pos != text_len:
        blocks.append(PlainBlock(
            start=last_end_pos,
            end=text_len,
            text=text[last_end_pos:]))

    return blocks


def _parse_line(line: str, offset: int, offset_bytes: int) -> list[Span]:
    index: int = 0
    length = len(line)
    stack: list[tuple[str, int]] = []
    spans: list[Span] = []

    while index < length:
        sd = line[index]
        if sd not in SPAN_DIRS:
            index += 1
            continue

        is_valid_start = _is_valid_span_start(line, index)
        is_valid_end = _is_valid_span_end(line, index)

        if is_valid_start and is_valid_end:
            # Favor end over new start, this means parsing is done non-greedy
            if sd in [open_sd for open_sd, _ in stack]:
                is_valid_start = False

        if is_valid_start:
            if sd == PRE:
                index = _handle_pre_span(line,
                                         index,
                                         offset,
                                         offset_bytes,
                                         spans)
                continue

            stack.append((sd, index))
            index += 1
            continue

        if is_valid_end:
            if sd not in [open_sd for open_sd, _ in stack]:
                index += 1
                continue

            if _is_span_empty(sd, index, stack):
                stack.pop()
                index += 1
                continue

            start_pos = _find_span_start_position(sd, stack)
            spans.append(_make_span(line,
                                    sd,
                                    start_pos,
                                    index,
                                    offset,
                                    offset_bytes))

        index += 1

    return spans


def _parse_uris(line: str, offset: int, offset_bytes: int) -> list[BaseUri]:
    uris: list[BaseUri] = []

    def make(match: Match[str], is_address: bool) -> BaseUri:
        return _make_link(line,
                          match.start(),
                          match.end() - 1,
                          offset,
                          offset_bytes,
                          is_address)

    for match in URI_RX.finditer(line):
        uri = make(match, False)
        uris.append(uri)

    for match in ADDRESS_RX.finditer(line):
        uri = make(match, True)
        uris.append(uri)

    return uris


def _parse_emojis(line: str, offset: int) -> list[Emoji]:
    emojis: list[Emoji] = []

    def make(match: Match[str]) -> Emoji:
        return _make_emoji(line,
                           match.start(),
                           match.end() - 1,
                           offset)

    for match in EMOJI_RX.finditer(line):
        emoji = make(match)
        emojis.append(emoji)

    return emojis


def _handle_pre_span(line: str,
                     index: int,
                     offset: int,
                     offset_bytes: int,
                     spans: list[Span]) -> int:

    # Scan ahead for the end
    end = line.find(PRE, index + 1)
    if end == -1:
        return index + 1

    if end - index == 1:
        # empty span
        return index + 1

    spans.append(_make_span(line, PRE, index, end, offset, offset_bytes))
    return end + 1


def _make_span(line: str,
               sd: str,
               start: int,
               end: int,
               offset: int,
               offset_bytes: int) -> Span:

    text = line[start:end + 1]

    start_byte = find_byte_index(line, start) + offset_bytes
    end_byte = find_byte_index(line, end) + offset_bytes + 1

    start += offset
    end += offset + 1
    span_class = SPAN_CLS_DICT.get(sd)
    assert span_class is not None

    return span_class(start=start,
                      start_byte=start_byte,
                      end=end,
                      end_byte=end_byte,
                      text=text)


def _make_link(line: str,
               start: int,
               end: int,
               offset: int,
               offset_bytes: int,
               is_address: bool) -> BaseUri:

    text = line[start:end + 1]

    start_byte = find_byte_index(line, start) + offset_bytes
    end_byte = find_byte_index(line, end) + offset_bytes + 1

    start += offset
    end += offset + 1

    if not is_address:
        cls_ = Uri

    elif text.startswith('xmpp'):
        cls_ = XMPPAddress

    elif text.startswith('mailto'):
        cls_ = MailAddress

    else:
        cls_ = Address

    return cls_(start=start,
                start_byte=start_byte,
                end=end,
                end_byte=end_byte,
                text=text)


def _make_emoji(line: str,
                start: int,
                end: int,
                offset: int) -> Emoji:
    text = line[start:end + 1]
    start += offset
    end += offset + 1
    return Emoji(start=start,
                 end=end,
                 text=text)


def _is_span_empty(sd: str, index: int, stack: list[tuple[str, int]]) -> bool:
    start_sd = stack[-1][SD]
    if start_sd != sd:
        return False

    pos = stack[-1][SD_POS]
    return pos == index - 1


def _find_span_start_position(sd: str, stack: list[tuple[str, int]]) -> int:
    while stack:
        start_sd, pos = stack.pop()
        if start_sd == sd:
            return pos

    raise ValueError('Unable to find opening span')


def _is_valid_span_start(line: str, index: int) -> bool:
    '''
    https://xmpp.org/extensions/xep-0393.html#span

    ... The opening styling directive MUST be located at the beginning
    of the line, after a whitespace character, or after a different opening
    styling directive. The opening styling directive MUST NOT be followed
    by a whitespace character ...
    '''

    try:
        char = line[index + 1]
    except IndexError:
        return False

    if char in WHITESPACE:
        return False

    if index == 0:
        return True

    char = line[index - 1]
    return char in VALID_SPAN_START


def _is_valid_span_end(line: str, index: int) -> bool:
    '''
    https://xmpp.org/extensions/xep-0393.html#span

    ... and the closing styling directive MUST NOT be preceded
    by a whitespace character ...
    '''

    if index == 0:
        return False

    char = line[index - 1]
    return char not in WHITESPACE
