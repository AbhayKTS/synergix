// background.js - service worker for the extension
// Minimal background to store settings and proxy messages if needed.

const DEFAULT_API = 'http://127.0.0.1:8080'

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(['apiUrl'], (res) => {
    if (!res.apiUrl) {
      chrome.storage.local.set({ apiUrl: DEFAULT_API })
    }
  })
})

// Simple message handler so popup can get/set apiUrl
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === 'getApiUrl') {
    chrome.storage.local.get(['apiUrl'], (res) => {
      sendResponse({ apiUrl: res.apiUrl || DEFAULT_API })
    })
    return true
  }
  if (msg && msg.type === 'setApiUrl') {
    chrome.storage.local.set({ apiUrl: msg.apiUrl }, () => sendResponse({ ok: true }))
    return true
  }
})
