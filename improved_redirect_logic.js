// 改进的论坛发帖跳转逻辑
// 替换现有的跳转代码部分

try {
    await ForumAPI.createPost(postData);

    const container = document.getElementById('toast-container');
    if (container) container.innerHTML = '';
    showToast('🎉 發布成功！', 'success', 2000);

    // 禁用按钮防止重复提交
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="w-4 h-4 animate-spin" data-lucide="loader-2"></i> 跳轉中...';
        if (window.lucide) lucide.createIcons();
    }

    // 使用多种方式确保跳转
    setTimeout(() => {
        // 尝试第一种跳转方式
        if (window.location && window.location.href) {
            try {
                window.location.href = '/static/forum/index.html';
            } catch (e) {
                console.error('Location href failed:', e);
                // 备用跳转方式
                window.location.replace('/static/forum/index.html');
            }
        } else {
            // 如果上述方式都失败，使用 window.open
            window.open('/static/forum/index.html', '_self');
        }
    }, 2000);

} catch (err) {
    showToast('發布失敗: ' + err.message, 'error');
    resetButton();
}