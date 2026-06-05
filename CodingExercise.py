import urllib.request
from html.parser import HTMLParser

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.grid = {}
        self.in_td = False
        self.current_row = []
        self.current_cell = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_td = True
            self.current_cell = ''

    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td = False
            self.current_row.append(self.current_cell.strip())
        elif tag == 'tr':
            if len(self.current_row) == 3:
                try:
                    x = int(self.current_row[0])
                    char = self.current_row[1]
                    y = int(self.current_row[2])
                    self.grid[(x, y)] = char
                except ValueError:
                    pass
            self.current_row = []

    def handle_data(self, data):
        if self.in_td:
            self.current_cell += data

def decode_secret_message(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')

    parser = TableParser()
    parser.feed(html)
    grid = parser.grid

    max_x = max(k[0] for k in grid)
    max_y = max(k[1] for k in grid)

    for y in range(max_y, -1, -1):
        print(''.join(grid.get((x, y), ' ') for x in range(max_x + 1)))

decode_secret_message("https://docs.google.com/document/d/e/2PACX-1vSvM5gDlNvt7npYHhp_XfsJvuntUhq184By5xO_pA4b_gCWeXb6dM6ZxwN8rE6S4ghUsCj2VKR21oEP/pub")