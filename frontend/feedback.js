const feedbackWidget = document.createElement('div');
feedbackWidget.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: #3b82f6;
    color: white;
    padding: 10px 15px;
    border-radius: 8px;
    cursor: pointer;
    z-index: 10000;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    font-weight: bold;
`;
feedbackWidget.innerText = "✏️ Додати коментар";
document.body.appendChild(feedbackWidget);

let isCommentingMode = false;

feedbackWidget.addEventListener('click', () => {
    isCommentingMode = !isCommentingMode;
    if(isCommentingMode) {
        feedbackWidget.style.background = '#ef4444';
        feedbackWidget.innerText = "❌ Скасувати режим";
        document.body.style.cursor = 'crosshair';
    } else {
        feedbackWidget.style.background = '#3b82f6';
        feedbackWidget.innerText = "✏️ Додати коментар";
        document.body.style.cursor = 'default';
    }
});

document.body.addEventListener('click', (e) => {
    if(!isCommentingMode || e.target === feedbackWidget) return;
    
    const commentBox = document.createElement('div');
    commentBox.style.cssText = `
        position: absolute;
        top: ${e.pageY}px;
        left: ${e.pageX}px;
        background: #fef08a;
        color: #1e293b;
        padding: 10px;
        border-radius: 4px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        z-index: 9999;
        min-width: 150px;
        border: 1px solid #eab308;
    `;
    
    const input = document.createElement('textarea');
    input.placeholder = "Ваш коментар...";
    input.style.cssText = "width: 100%; border: none; background: transparent; outline: none; resize: both;";
    
    const closeBtn = document.createElement('button');
    closeBtn.innerText = "×";
    closeBtn.style.cssText = "position: absolute; top: 0; right: 5px; background: none; border: none; cursor: pointer; font-size: 16px; font-weight: bold;";
    closeBtn.onclick = () => commentBox.remove();
    
    commentBox.appendChild(closeBtn);
    commentBox.appendChild(input);
    document.body.appendChild(commentBox);
    input.focus();
    
    isCommentingMode = false;
    feedbackWidget.style.background = '#3b82f6';
    feedbackWidget.innerText = "✏️ Додати коментар";
    document.body.style.cursor = 'default';
});
