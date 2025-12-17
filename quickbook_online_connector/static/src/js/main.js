function convertStringToHTML(htmlString) {
    const parser = new DOMParser();
    const html = parser.parseFromString(htmlString, 'text/html');
    return html.body;
}

document.getElementById('quickbook_partner').innerHTML = convertStringToHTML(document.getElementById('quickbook_partner').textContent).innerHTML;
document.getElementById('quickbook_category').innerHTML = convertStringToHTML(document.getElementById('quickbook_category').textContent).innerHTML;
document.getElementById('quickbook_invoice').innerHTML = convertStringToHTML(document.getElementById('quickbook_invoice').textContent).innerHTML;
document.getElementById('quickbook_product').innerHTML = convertStringToHTML(document.getElementById('quickbook_product').textContent).innerHTML;   
