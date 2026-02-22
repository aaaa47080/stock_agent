import re

file_path = 'd:/okx/stock_agent/web/js/components.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'<\s+div', '<div', content)
content = re.sub(r'div\s+>', 'div>', content)
content = re.sub(r'<\s+!--', '<!--', content)
content = re.sub(r'--\s+>', '-->', content)
content = content.replace('<div id = "', '<div id="')
content = content.replace('</div >', '</div>')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
