// contentScript.js
// Injects a page script that wraps window.ethereum.request to intercept transaction/sign requests.
// Listens for postMessage events from the page script, queries the API gateway, shows an in-page modal
// with risk info, and posts the user's decision back to the page script so it can continue or cancel the request.

(function(){
  const INJECTED_FUNCTION_NAME = '__ai_oracle_injected'
  // Inject page script
  const scriptContent = `
  (function(){
    if (window.${INJECTED_FUNCTION_NAME}) return;
    window.${INJECTED_FUNCTION_NAME} = true;
    const provider = window.ethereum;
    if(!provider) return;
    const originalRequest = provider.request.bind(provider);
    window.__ai_oracle_pending = {};
    let idCounter = 1;

    provider.request = function(payload){
      try{
        const method = payload.method || (payload && payload[0]) || '';
        const params = payload.params || payload.arguments || [];
        // Interested in transaction sending and signing methods
        const interesting = ['eth_sendTransaction','eth_signTransaction','eth_sign','personal_sign','eth_signTypedData','eth_signTypedData_v4'];
        if (interesting.includes(method)){
          // extract target address if possible
          let target = null;
          if (method === 'eth_sendTransaction' && params[0] && params[0].to) target = params[0].to;
          if (!target && params[0] && typeof params[0] === 'string'){
            // sometimes personal_sign params: [message, address]
            target = null;
          }
          const reqId = 'ai-'+(idCounter++);
          // send message to content script for risk check
          window.postMessage({
            source: 'ai-oracle-extension',
            type: 'sign_request',
            reqId,
            method,
            params,
            target
          }, '*');

          // Return a promise that will be resolved/rejected by decision from extension
          return new Promise((resolve, reject) => {
            window.__ai_oracle_pending[reqId] = {resolve, reject, originalPayload: payload};
            // set small timeout to avoid hanging indefinitely (e.g., 2 minutes)
            setTimeout(()=>{
              if(window.__ai_oracle_pending[reqId]){
                delete window.__ai_oracle_pending[reqId];
                reject(new Error('User did not respond to risk prompt'));
              }
            }, 120000);
          });
        }
      }catch(e){
        console.warn('AI Oracle wrapper error', e);
      }
      // default
      return originalRequest(payload);
    };

    // listener for decisions from content script
    window.addEventListener('message', (ev)=>{
      if(!ev.data || ev.data.source !== 'ai-oracle-extension') return;
      if(ev.data.type === 'sign_decision'){
        const { reqId, allow } = ev.data;
        const pending = window.__ai_oracle_pending && window.__ai_oracle_pending[reqId];
        if(!pending) return;
        const { resolve, reject, originalPayload } = pending;
        delete window.__ai_oracle_pending[reqId];
        if(allow){
          // Proceed by calling original provider.request
          originalRequest(originalPayload).then(resolve).catch(reject);
        } else {
          reject(new Error('User blocked the transaction based on risk warning'));
        }
      }
    });
  })();
  `

  const s = document.createElement('script')
  s.textContent = scriptContent
  ;(document.head || document.documentElement).appendChild(s)
  s.remove()

  // Listen for messages from the page
  window.addEventListener('message', async (ev)=>{
    try{
      if(!ev.data || ev.data.source !== 'ai-oracle-extension' || ev.data.type !== 'sign_request') return;
      const { reqId, method, params, target } = ev.data

      // Determine contract address
      let contractAddress = target || null
      if(!contractAddress){
        // try to parse params for common patterns
        if(params && params[0] && params[0].to) contractAddress = params[0].to
      }

      // get api url from storage
      chrome.runtime.sendMessage({type:'getApiUrl'}, async (resp) => {
        const api = (resp && resp.apiUrl) ? resp.apiUrl : 'http://127.0.0.1:8080'
        let risk = null
        if(contractAddress){
          try{
            const url = api.replace(/\/$/, '') + '/risk/' + encodeURIComponent(contractAddress)
            const r = await fetch(url, {cache:'no-cache'})
            if(r.ok) risk = await r.json()
          }catch(e){
            console.warn('AI oracle fetch failed', e)
          }
        }

        // show in-page modal
        const decision = await showRiskModal({contractAddress, method, params, risk})
        // send decision back to page script
        window.postMessage({source:'ai-oracle-extension', type:'sign_decision', reqId, allow: decision.allow}, '*')
      })
    }catch(e){
      console.warn('contentScript message handler error', e)
    }
  })

  // Create an in-page modal and return a Promise resolved when user selects allow/block
  function showRiskModal({contractAddress, method, params, risk}){
    return new Promise((resolve)=>{
      // create overlay
      const overlayId = 'ai-oracle-overlay'
      if(document.getElementById(overlayId)){
        // if already open, resolve allow false
        resolve({allow:false})
        return
      }
      const overlay = document.createElement('div')
      overlay.id = overlayId
      Object.assign(overlay.style, {
        position:'fixed', left:0, right:0, top:0, bottom:0, background:'rgba(0,0,0,0.5)', zIndex: 2147483647, display:'flex', alignItems:'center', justifyContent:'center'
      })
      const card = document.createElement('div')
      Object.assign(card.style, {background:'#0b1220', color:'#e6eef8', padding:'16px', borderRadius:'8px', width:'480px', boxShadow:'0 10px 30px rgba(0,0,0,0.6)'})
      const title = document.createElement('div')
      title.textContent = 'AI Oracle Risk Warning'
      Object.assign(title.style, {fontSize:'18px', fontWeight:700, marginBottom:'8px'})
      const addr = document.createElement('div')
      addr.textContent = 'Contract: ' + (contractAddress || 'unknown')
      addr.style.marginBottom = '8px'

      const scoreLine = document.createElement('div')
      const scoreText = risk && typeof risk.risk_score === 'number' ? Math.round(risk.risk_score * 100) + '%': 'N/A'
      const label = risk && risk.risk_label ? risk.risk_label : 'unknown'
      scoreLine.textContent = `Risk: ${scoreText} (${label})`
      scoreLine.style.marginBottom = '8px'

      const oneLine = document.createElement('div')
      oneLine.style.marginBottom = '12px'
      oneLine.style.fontSize = '13px'
      oneLine.style.color = '#98a1b3'
      oneLine.textContent = (risk && risk.details && risk.details.reason) ? risk.details.reason : (risk && risk.feature_details ? 'AI explanation available' : 'No explanation available')

      const btnAllow = document.createElement('button')
      btnAllow.textContent = 'Allow'
      Object.assign(btnAllow.style, {marginRight:'8px', padding:'8px 12px', borderRadius:'6px', cursor:'pointer'})
      const btnBlock = document.createElement('button')
      btnBlock.textContent = 'Block'
      Object.assign(btnBlock.style, {padding:'8px 12px', borderRadius:'6px', cursor:'pointer', background:'#8b0000', color:'#fff'})

      btnAllow.addEventListener('click', ()=>{ cleanup(); resolve({allow:true}) })
      btnBlock.addEventListener('click', ()=>{ cleanup(); resolve({allow:false}) })

      card.appendChild(title)
      card.appendChild(addr)
      card.appendChild(scoreLine)
      card.appendChild(oneLine)
      const btns = document.createElement('div')
      btns.appendChild(btnAllow); btns.appendChild(btnBlock)
      card.appendChild(btns)
      overlay.appendChild(card)
      document.documentElement.appendChild(overlay)

      function cleanup(){
        try{ overlay.remove() }catch(e){}
      }
    })
  }

})();
