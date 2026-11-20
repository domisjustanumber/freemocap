import React from 'react';
import {type Block, parseInline, parseReportMarkdown} from '@/services/server/report-markdown';

const line = (text: string) => parseInline(text).map((part, index) => part.kind === 'bold' ? <strong key={index}>{part.text}</strong>
    : part.kind === 'code' ? <code key={index} style={{fontFamily: 'var(--font-mono)'}}>{part.text}</code> : part.text);

const cell = {padding: '2px 8px', border: '1px solid var(--color-border-control)', textAlign: 'left' as const};

function BlockView({block}: {block: Block}) {
    switch (block.kind) {
        case 'heading': return block.level === 1 ? <h2 className="text-white" style={{fontSize: 18, margin: 0}}>{line(block.text)}</h2>
            : <h3 className="text-white" style={{fontSize: 15, margin: 0}}>{line(block.text)}</h3>;
        case 'paragraph': return <p className="text sm text-white">{block.lines.map((text, index) =>
            <React.Fragment key={index}>{index > 0 && <br/>}{line(text)}</React.Fragment>)}</p>;
        case 'list': return <ul className="text sm text-white" style={{paddingLeft: 20, listStyle: 'disc'}}>
            {block.items.map((item, index) => <li key={index}>{line(item)}</li>)}</ul>;
        case 'quote': return <blockquote className="text sm text-gray" style={{borderLeft: '3px solid var(--color-border-control)', paddingLeft: 8, margin: 0}}>
            {block.lines.map((text, index) => <React.Fragment key={index}>{index > 0 && <br/>}{line(text)}</React.Fragment>)}</blockquote>;
        case 'table': return <table className="text sm text-white" style={{borderCollapse: 'collapse'}}>
            <thead><tr>{block.header.map((text, index) => <th key={index} style={cell}>{line(text)}</th>)}</tr></thead>
            <tbody>{block.rows.map((row, rowIndex) => <tr key={rowIndex}>
                {row.map((text, index) => <td key={index} style={cell}>{line(text)}</td>)}</tr>)}</tbody>
        </table>;
        case 'code': return <pre className="text sm text-white bg-dark p-1 br-1"
                                 style={{maxHeight: '35vh', overflow: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)'}}>{block.text}</pre>;
    }
}

/** The report file as written by the server, read as Markdown: the summary on top, the data block (own scroll) below. */
export function ReportMarkdown({text}: {text: string}) {
    return <div className="flex flex-col gap-2">{parseReportMarkdown(text).map((block, index) => <BlockView key={index} block={block}/>)}</div>;
}
