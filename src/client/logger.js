const logger = (payload) => {
    const parent = document.querySelector('#console');
    const log = document.createElement('div');
    log.setAttribute('class', 'log ' + (payload.type || ''));
    const date = new Date();
    log.innerHTML = `
        ${payload?.message ? `<div>${payload.message}</div>` : ''}
        <div class="actions"></div>
        <small>${date.toLocaleDateString() + ' - ' + date.toLocaleTimeString()}</small>
    `;
    parent.appendChild(log);
    const actions = log.querySelector('.actions');
    if (actions && payload?.options?.action?.type === 'popup') {
        const button = document.createElement('button');
        button.onclick = () => {
            window.open(payload.options.action.link, '', 'popup=true,width=800,height=600');
        };
        button.innerText = payload.options.action.label;
        actions.appendChild(button);
    }
    parent.scrollTo(0, parent.scrollHeight);
}

export default logger;
