document.addEventListener('DOMContentLoaded', ()=>{
  const apiInput = document.getElementById('apiUrl')
  const saveBtn = document.getElementById('save')

  chrome.runtime.sendMessage({type:'getApiUrl'}, (resp)=>{
    apiInput.value = (resp && resp.apiUrl) ? resp.apiUrl : ''
  })

  saveBtn.addEventListener('click', ()=>{
    const api = apiInput.value.trim()
    chrome.runtime.sendMessage({type:'setApiUrl', apiUrl: api}, (r)=>{
      saveBtn.textContent = 'Saved'
      setTimeout(()=> saveBtn.textContent = 'Save', 1200)
    })
  })
})
