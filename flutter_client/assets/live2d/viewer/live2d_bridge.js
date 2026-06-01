(function () {
  function notifyFlutter(payload) {
    const message = JSON.stringify(payload);
    if (window.Live2DChannel && typeof window.Live2DChannel.postMessage === "function") {
      window.Live2DChannel.postMessage(message);
    }
    if (
      window.chrome &&
      window.chrome.webview &&
      typeof window.chrome.webview.postMessage === "function"
    ) {
      window.chrome.webview.postMessage(message);
    }
  }

  window.__live2dNotifyFlutter = notifyFlutter;
})();
