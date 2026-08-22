from pathlib import Path

path = Path('preview/governance-dashboard/Dockerfile')
text = path.read_text()

anchor = 'COPY finops-polish.js /usr/share/nginx/html/finops-polish.js\n'
insert = (
    anchor
    + 'COPY quality.js /usr/share/nginx/html/quality.js\n'
    + 'COPY quality.css /usr/share/nginx/html/quality.css\n'
)

if 'COPY quality.js /usr/share/nginx/html/quality.js' in text and 'COPY quality.css /usr/share/nginx/html/quality.css' in text:
    print('PASS: quality.js y quality.css ya estaban incluidos en Dockerfile.')
else:
    if anchor not in text:
        raise SystemExit('FAIL: no se encontró el punto canónico de inserción en Dockerfile')
    text = text.replace(anchor, insert, 1)
    path.write_text(text)
    print('PASS: Dockerfile del preview ahora empaqueta quality.js y quality.css.')
    print('El smoke test existente ya valida ambos assets desplegados.')
