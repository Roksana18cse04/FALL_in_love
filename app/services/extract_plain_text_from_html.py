from html.parser import HTMLParser

class HTMLToText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    
    def handle_data(self, data):
        self.text.append(data)
    
    def get_text(self):
        return ''.join(self.text).strip()
    
async def extract_plain_text(html_text: str):
    parser = HTMLToText()
    parser.feed(html_text)
    plain_text = parser.get_text()
    return plain_text