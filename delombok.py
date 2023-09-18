import sys
import re
import subprocess
import re
from os.path import realpath, dirname, join, isdir
from os import walk, makedirs

INSERT_COST = 1
DELETE_COST = INSERT_COST

NONE = 0
INSERT = 1
DELETE = 2
MATCH = 3

lombokjar = join(dirname(realpath(__file__)), 'lombok.jar')


def lineending(s):
  if s[-2:] == '\r\n':
    return '\r\n'
  elif s[-1:] == '\n':
    return '\n'
  else:
    return ''


def comp(el1, el2):
  if el1 == el2:
    return 0
  elif el1.strip() == el2.strip():
    return 0.1
  else:
    return 2.1


def match(s1, s2):
  m = [[(0, NONE) for i in range(len(s2) + 1)] for j in range(len(s1) + 1)]
  for x in range(len(s1) + 1):
    for y in range(len(s2) + 1):
      if x == 0:
        if y == 0:
          m[x][y] = (0, NONE)
        else:
          m[x][y] = (m[x][y-1][0] + INSERT_COST, INSERT)
      else:
        if y == 0:
          m[x][y] = (m[x-1][y][0] + DELETE_COST, DELETE)
        else:
          m[x][y] = min(
            (m[x-1][y][0] + DELETE_COST, DELETE),
            (m[x][y-1][0] + INSERT_COST, INSERT),
            (m[x-1][y-1][0] + comp(s1[x-1], s2[y-1]), MATCH)
          )

  x, y = len(s1), len(s2)
  outbuf = ''
  mergebuf = ''
  while x > 0 or y > 0:
    mod = m[x][y][1]
    if mod == DELETE:
      outbuf = merge(lineending(s1[x-1]), mergebuf) + outbuf
      mergebuf = ''
      x = x - 1
    elif mod == INSERT:
      mergebuf = merge(s2[y-1], mergebuf)
      y = y - 1
    elif mod == MATCH:
      outbuf = merge(s1[x-1], mergebuf) + outbuf
      mergebuf = ''
      x = x - 1
      y = y - 1
    else:
      raise Exception('Internal Error!')

  if len(mergebuf) > 0:
    outbuf = mergebuf + outbuf

  return outbuf


class Element:
  def __init__(self, code, schar, echar):
    self.code = code
    self.schar = schar
    self.echar = echar

  def getLines(self):
    return re.split('\r?\n', self.code)

  def getText(self):
    return self.code[self.schar:self.echar + 1]

  def __str__(self):
    return self.__class__.__name__ + '(\n' + self.getText() + '\n)'


class LineComment(Element):
  def __init__(self, code, schar, echar):
    super().__init__(code, schar, echar)

  def getFilteredText(self):
    return '/*' + super().getText()[2:].replace('*', '/') + '*/'

class BlockComment(Element):
  def __init__(self, code, schar, echar):
    super().__init__(code, schar, echar)

  def getFilteredText(self):
    return super().getText()

class StringLiteral(Element):
  def __init__(self, code, schar, echar):
    super().__init__(code, schar, echar)

  def getFilteredText(self):
    return super().getText()

class MultiLineStringLiteral(Element):
  def __init__(self, code, schar, echar):
    super().__init__(code, schar, echar)

  def getFilteredText(self):
    return '"" /*' + super().getText()[3:-3].replace('*', '/') + '*/'


def parse(code):
  elements = []
  idx = 0
  while idx < len(code):
    sidx = idx
    idx = parse_line_comment(code, idx, elements)
    if idx != sidx:
      continue

    idx = parse_block_comment(code, idx, elements)
    if idx != sidx:
      continue
    idx = parse_multiline_string_literal(code, idx, elements)
    if idx != sidx:
      continue
    idx = parse_string_literal(code, '"', idx, elements)
    if idx != sidx:
      continue
    idx = parse_string_literal(code, "'", idx, elements)
    if idx != sidx:
      continue

    if idx == sidx:
      idx = idx + 1
  return elements

def parse_line_comment(code, idx, elements):
  offset = idx + 2
  if code[idx:offset] != '//':
    return idx
  for ch in code[offset:]:
    if ch == "\n":
      break
    offset = offset + 1

  if offset >= len(code):
    offset = len(code) - 1
  elif code[offset] == '\n':
    offset = offset - 1
    if code[offset] == '\r':
      offset = offset - 1
  elements.append(LineComment(code, idx, offset))
  return offset + 1

def parse_block_comment(code, idx, elements):
  offset = idx + 2
  if code[idx:offset] != '/*':
    return idx
  for i in range(offset, len(code)):
    if code[i:i+2] == '*/':
      elements.append(BlockComment(code, idx, i + 1))
      return i + 2
  raise Exception("Block comment not closed!: " + code[idx:len(code)])

def parse_string_literal(code, character, idx, elements):
  if code[idx] != character:
    return idx
  offset = idx + 1
  escaping = False
  for i in range(offset, len(code)):
    if code[i] == '\\':
      escaping = not escaping
    elif code[i] == character and not escaping:
      elements.append(StringLiteral(code, idx, i))
      return i + 1
    else:
      escaping = False
  raise Exception("String Literal not closed!: " + code[idx:len(code)])


def parse_multiline_string_literal(code, idx, elements):
  offset = idx + 3
  if code[idx:offset] != '"""' :
    return idx

  for ch in code[offset:]:
    offset = offset + 1
    if ch == '\n':
      break
    elif ch in ' \t\r':
      continue
    else:
      raise Exception('Multiline string literal, expected whitespace or linebreak!')

  escaping = False
  for i in range(offset, len(code)):
    if code[i] == '\\':
      escaping = not escaping
    elif code[i:i+3] == '"""' and not escaping:
      elements.append(MultiLineStringLiteral(code, idx, i + 2))
      return i + 3
    else:
      escaping = False

  raise Exception("Multiline string literal not closed!: " + code[idx, len(code)])


def normalize(code, elements):
  end = 0
  result = ''
  for e in elements:
    result = result + code[end:e.schar] + e.getFilteredText()
    end = e.echar + 1
  result = result + code[end:len(code)]
  return result


def merge(l1, l2):
  if len(l2) == 0:
    return l1
  return l1[0:len(l1)-len(lineending(l1))] + ' ' + l2


def writeFile(path, contents):
  with open(path, 'w') as f:
    print(
      contents,
      end='',
      file=f
    )


def main():
  if len(sys.argv) != 3:
    print('Usage: ' + sys.argv[0] + ' <srcDir> <outDir>', file=sys.stderr)
    return

  srcDir = sys.argv[1]
  if not srcDir.endswith('/'):
    srcDir = srcDir + '/'
  outDir = sys.argv[2]
  if not outDir.endswith('/'):
    outDir = outDir + '/'

  if not isdir(srcDir):
    print(srcDir + ' is not a directory!', file=sys.stderr)
    return

  makedirs(outDir)

  compiledRe = re.compile('^\s*import(\s+static)?\s+lombok(\.|\s|;|$)', re.MULTILINE)

  normalisedOriginalJavaFiles = {}

  for root, _, files in walk(srcDir):
    for file in files:
      if file.lower().endswith('.java'):
        relativeSrcPath = join(root.removeprefix(srcDir), file)
        absPath = join(root, file)
        with open(absPath, 'r') as f:
          original = f.read()
          if compiledRe.search(original):
            print('Found Lombok code in ' + relativeSrcPath, file=sys.stdout)
            normalisedOriginalJavaFiles[relativeSrcPath] = normalize(original, parse(original))

  delombokArgs = [
    'java',
    '-jar', lombokjar,
    'delombok',
    '-f', 'suppressWarnings:skip',
    '-f', 'generated:skip',
    '-f', 'generateDelombokComment:skip',
    srcDir,
    '-d', outDir
  ]

  print(' '.join(delombokArgs), file=sys.stderr)

  subprocess.run(
    delombokArgs,
    check=True
  )

  # if delomboked.strip() == '':
  #   print('WARNING: Delombok returned an empty string for ' + inputFile + ' !', file=sys.stderr)

  for relativeSrcPath in normalisedOriginalJavaFiles.keys():
    delombokedAbsPath = join(outDir, relativeSrcPath)
    with open(delombokedAbsPath, 'r') as f:
      delomboked = f.read()
      normalizedDelomboked = normalize(delomboked, parse(delomboked))
      print('Writing back to ' + relativeSrcPath, file=sys.stdout)
      writeFile(
        join(srcDir, relativeSrcPath),
        match(
          normalisedOriginalJavaFiles[relativeSrcPath].splitlines(keepends=True),
          normalizedDelomboked.splitlines(keepends=True)
        )
      )

main()
