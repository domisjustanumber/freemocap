/**
 * A tiny Markdown reader for the certify report file, for exactly what skellycertify's file writer emits: `#`/`##`
 * headings, paragraphs, `- ` lists, `> ` quotes, pipe tables (`\|` escaped in a cell), one fenced code block of any
 * fence length, and inline `**bold**` and `code`. It returns plain data; the component builds React elements from it,
 * so text typed by a person (the note) is always shown as text. No HTML is ever interpreted.
 */
export type Inline = {kind: 'text' | 'bold' | 'code'; text: string};
export type Block =
    | {kind: 'heading'; level: number; text: string}
    | {kind: 'paragraph'; lines: string[]}
    | {kind: 'list'; items: string[]}
    | {kind: 'quote'; lines: string[]}
    | {kind: 'table'; header: string[]; rows: string[][]}
    | {kind: 'code'; language: string; text: string};

const cells = (line: string) => line.trim().replace(/^\|/, '').replace(/(?<!\\)\|$/, '')
    .split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, '|'));
const isTableRule = (line: string) => /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$/.test(line.trim());

export function parseReportMarkdown(text: string): Block[] {
    const lines = text.replace(/\r\n?/g, '\n').split('\n');
    const blocks: Block[] = [];
    let index = 0;
    while (index < lines.length) {
        const line = lines[index];
        const fence = /^(`{3,})(\S*)\s*$/.exec(line);
        if (fence) {
            const body: string[] = [];
            for (index++; index < lines.length && lines[index].trim() !== fence[1]; index++) body.push(lines[index]);
            blocks.push({kind: 'code', language: fence[2], text: body.join('\n')});
            index++;
        } else if (/^#{1,6} /.test(line)) {
            const level = line.indexOf(' ');
            blocks.push({kind: 'heading', level, text: line.slice(level + 1).trim()});
            index++;
        } else if (line.trim().startsWith('|') && index + 1 < lines.length && isTableRule(lines[index + 1])) {
            const header = cells(line), rows: string[][] = [];
            for (index += 2; index < lines.length && lines[index].trim().startsWith('|'); index++) rows.push(cells(lines[index]));
            blocks.push({kind: 'table', header, rows});
        } else if (/^[-*] /.test(line)) {
            const items: string[] = [];
            for (; index < lines.length && /^[-*] /.test(lines[index]); index++) items.push(lines[index].slice(2));
            blocks.push({kind: 'list', items});
        } else if (/^>/.test(line)) {
            const quoted: string[] = [];
            for (; index < lines.length && /^>/.test(lines[index]); index++) quoted.push(lines[index].replace(/^> ?/, ''));
            blocks.push({kind: 'quote', lines: quoted});
        } else if (line.trim()) {
            const paragraph: string[] = [];
            for (; index < lines.length && lines[index].trim() && !/^(#{1,6} |[-*] |>|`{3,}|\|)/.test(lines[index]); index++) {
                paragraph.push(lines[index]);
            }
            if (!paragraph.length) paragraph.push(lines[index++]);  // a lone "|" line that is not a table
            blocks.push({kind: 'paragraph', lines: paragraph});
        } else index++;
    }
    return blocks;
}

/** `**bold**` and `code` spans of one line; everything else is text. */
export function parseInline(line: string): Inline[] {
    return line.split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).map(part =>
        part.startsWith('**') && part.endsWith('**') && part.length > 4 ? {kind: 'bold', text: part.slice(2, -2)}
            : part.startsWith('`') && part.endsWith('`') && part.length > 2 ? {kind: 'code', text: part.slice(1, -1)}
                : {kind: 'text', text: part});
}
