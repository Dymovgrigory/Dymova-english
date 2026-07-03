"""Мини-минификатор блоков Tilda: убирает верхний HTML-комментарий,
склеивает строки и уплотняет пробелы между тегами. Пишет *_min.html.
Использование: python3 minify_block.py <src.html> <out_min.html>
"""
import re, sys

def minify(src: str) -> str:
    # убрать HTML-комментарии блока
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    # склеить переносы строк и отступы в один пробел
    s = re.sub(r'\n\s*', ' ', src)
    # уплотнить пробелы между тегами
    s = re.sub(r'>\s+<', '><', s)
    # схлопнуть кратные пробелы
    s = re.sub(r'[ \t]{2,}', ' ', s)
    return s.strip()

if __name__ == '__main__':
    inp, out = sys.argv[1], sys.argv[2]
    with open(inp, encoding='utf-8') as f:
        data = f.read()
    res = minify(data)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(res)
    print(f"{out}: {len(res)} chars")
