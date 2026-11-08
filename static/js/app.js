"use strict";
document.querySelectorAll('nav a').forEach(a => {if(a.pathname===location.pathname)a.classList.add('active');});
document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {try{await navigator.clipboard.writeText(button.dataset.copy);button.textContent='Ссылка скопирована';}catch{window.prompt('Скопируйте ссылку:',button.dataset.copy);}}));
document.querySelectorAll('[data-print]').forEach(b=>b.addEventListener('click',()=>window.print()));
document.querySelectorAll('[data-confirm]').forEach(b=>b.addEventListener('click',e=>{if(!window.confirm(b.dataset.confirm))e.preventDefault();}));
document.querySelectorAll('[data-logout]').forEach(form=>form.addEventListener('submit',async e=>{e.preventDefault();if(!confirm('Выйти? Локальные данные сканера будут удалены. Перед выходом синхронизируйте отметки.'))return;try{if(indexedDB.databases){for(const db of await indexedDB.databases())if(db.name.startsWith('kulisy-'))indexedDB.deleteDatabase(db.name);}if('caches' in window){for(const key of await caches.keys())if(key.startsWith('kulisy-'))await caches.delete(key);}}finally{form.submit();}}));
