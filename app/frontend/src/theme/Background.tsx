import React, {useEffect, useState, useSyncExternalStore} from 'react';

type Background = {blob?: Blob; rendered?: Blob; renderVersion?: number; name: string; opacity: number; blur: number};
let current: Background = {name:'', opacity:55, blur:2};
let ready: Promise<void> | undefined;
const listeners = new Set<()=>void>();
function publish(next: Background) { current=next; listeners.forEach(fn=>fn()); }
async function bake(value: Background): Promise<Background> {
  if (!value.blob) return {...value,rendered:undefined,renderVersion:1};
  const bitmap=await createImageBitmap(value.blob);
  try {
    if (bitmap.width*bitmap.height>40_000_000) throw Error('图片不能超过 4000 万像素。');
    const scale=Math.min(1,2560/Math.max(bitmap.width,bitmap.height));
    const canvas=document.createElement('canvas');
    canvas.width=Math.max(1,Math.round(bitmap.width*scale)); canvas.height=Math.max(1,Math.round(bitmap.height*scale));
    const ctx=canvas.getContext('2d');
    if(!ctx) throw Error('浏览器无法生成静态背景。');
    ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
    // Bake blur into pixels only when the user saves, never into the page compositor.
    if(value.blur>0) {ctx.filter=`blur(${value.blur}px)`;const pad=value.blur*3;ctx.drawImage(bitmap,-pad,-pad,canvas.width+pad*2,canvas.height+pad*2);}
    const rendered=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error('静态背景生成失败。')),'image/webp',.9));
    canvas.width=canvas.height=1;
    return {...value,rendered,renderVersion:1};
  } finally {bitmap.close();}
}
function database(): Promise<IDBDatabase> {
  return new Promise((resolve,reject)=>{const req=indexedDB.open('demo-lab-background',1); req.onupgradeneeded=()=>req.result.createObjectStore('settings'); req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(req.error);});
}
async function read() { const db=await database(); try { return await new Promise<Background|undefined>((resolve,reject)=>{const req=db.transaction('settings').objectStore('settings').get('background'); req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(req.error);}); } finally {db.close();} }
async function save(value: Background) { const db=await database(); try {await new Promise<void>((resolve,reject)=>{const tx=db.transaction('settings','readwrite'); tx.objectStore('settings').put(value,'background'); tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});publish(value);} finally {db.close();} }
function useBackground() {
  const value=useSyncExternalStore(fn=>{listeners.add(fn);return ()=>{listeners.delete(fn);};},()=>current);
  const [error,setError]=useState('');
  useEffect(()=>{ready ??= read().then(async value=>{if(value) {if(value.blob && (!value.rendered || value.renderVersion!==1)) await save(await bake(value));else publish(value);}});ready.catch(()=>setError('背景读取失败，请重新选择图片或检查站点存储权限。'));},[]);
  return {value,error,setError};
}
export function useBackgroundLayer() {
  const {value}=useBackground();
  useEffect(()=>{
    const root=document.documentElement;
    const url=value.rendered ? URL.createObjectURL(value.rendered) : '';
    root.dataset.wallpaper=url ? 'on' : 'off';
    root.style.setProperty('--wallpaper',url ? `url("${url}")` : 'none');
    root.style.setProperty('--wallpaper-opacity',String(value.opacity/100));
    return ()=>{if(url)URL.revokeObjectURL(url);};
  },[value]);
}
export function BackgroundPanel() {
  const {value,error,setError}=useBackground();
  const [busy,setBusy]=useState(false);
  const [blur,setBlur]=useState(value.blur);
  useEffect(()=>setBlur(value.blur),[value.blur]);
  async function commit(next:Background,render=false) {setBusy(true);setError('');try {await ready?.catch(()=>{});await save(render?await bake(next):next);}catch {setError('背景保存失败，可能是浏览器存储空间不足。');}finally{setBusy(false);}}
  async function select(file?:File) {
    if(!file)return;
    if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>12*1024*1024) {setError('请选择不超过 12 MB 的 JPG、PNG 或 WebP 图片。');return;}
    setBusy(true);setError('');
    try {await ready?.catch(()=>{});await save(await bake({...current,blob:file,name:file.name}));}
    catch(e){setError(e instanceof Error ? e.message : '无法读取或保存这张图片。');}finally{setBusy(false);}
  }
  return <section className="settings-section wallpaper-settings">
    <div className="settings-heading"><h3>背景图片</h3><small>只保存在当前浏览器，不上传服务器</small></div>
    <label className="wallpaper-picker">{busy?'正在保存…':'选择背景图片'}<input aria-label="上传背景图片" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={e=>{void select(e.target.files?.[0]);e.target.value='';}}/></label>
    <p className="muted">{value.name || '未设置背景 · JPG / PNG / WebP，最大 12 MB'}</p>
    {value.blob && <><label className="wallpaper-range">图片强度 <span>{value.opacity}%</span><input aria-label="背景图片强度" type="range" min="10" max="100" value={value.opacity} disabled={busy} onChange={e=>void commit({...value,opacity:Number(e.target.value)})}/></label>
    <label className="wallpaper-range">背景柔化 <span>{blur}</span><input aria-label="背景柔化" type="range" min="0" max="20" value={blur} disabled={busy} onChange={e=>setBlur(Number(e.target.value))}/></label>
    <button disabled={busy || blur===value.blur} onClick={()=>void commit({...value,blur},true)}>保存静态背景</button>
    <p className="muted">仅保存时处理一次，浏览页面时不实时模糊。</p>
    <button disabled={busy} onClick={()=>void commit({name:'',opacity:55,blur:2})}>移除背景图片</button></>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
