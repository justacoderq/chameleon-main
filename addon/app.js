const $ = id => document.getElementById(id);
let source = null, result = null, samples = {}, sdk = null;
const status = message => { $("status").textContent = message; };
function setSource(task) {
  source = task.source || task;
  if (!source.canvas || !Array.isArray(source.elements)) throw new Error("Choose a Chameleon design or task JSON.");
  $("source-info").textContent = source.elements.length + " elements · " + source.canvas.width + " × " + source.canvas.height;
  $("resize").disabled = false;
  $("result").hidden = true;
}
async function request(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Local engine request failed.");
  return data;
}
function save(blob, name) {
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function pngBlob(encoded) {
  return new Blob([Uint8Array.from(atob(encoded), c => c.charCodeAt(0))], {type:"image/png"});
}
$("sample").addEventListener("change", () => { if (samples[$("sample").value]) setSource(samples[$("sample").value]); });
$("file").addEventListener("change", async event => {
  try { if (event.target.files[0]) setSource(JSON.parse(await event.target.files[0].text())); }
  catch(error) { source = null; $("resize").disabled = true; status(error.message); }
});
$("format").addEventListener("change", () => { const [w,h] = $("format").value.split(","); $("width").value=w; $("height").value=h; });
$("resize").addEventListener("click", async () => {
  $("resize").disabled = true; $("result").hidden = true; status("Finding a layout for your canvas…");
  try {
    const width=Number($("width").value), height=Number($("height").value);
    if (![width,height].every(n => Number.isInteger(n) && n>0 && n<=4096)) throw new Error("Choose dimensions from 1 to 4096 pixels.");
    result = await request("resize",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source,target_canvas:{width,height}})});
    $("preview").src = "data:image/png;base64," + result.png;
    $("result").hidden = false;
    const warnings = result.audit.quality_warnings;
    $("quality").textContent = warnings.length ? "Review needed: " + warnings.join("; ") : "All elements retained. No measured overflow or collisions detected; review the design by eye.";
    $("details").textContent = JSON.stringify({renderer:result.renderer,model:result.diagnostics.model,layout:result.diagnostics.selected,warnings:result.warnings},null,2);
    status(result.renderer === "pillow" ? "Development preview ready. Official rendering still needs verification." : "Your adapted design is ready.");
  } catch(error) { status(error.message); }
  finally { $("resize").disabled = !source; }
});
$("show-source").addEventListener("click",()=>{ $("preview").src="data:image/png;base64,"+result.source_png; });
$("show-result").addEventListener("click",()=>{ $("preview").src="data:image/png;base64,"+result.png; });
$("download").addEventListener("click",()=>save(new Blob([JSON.stringify(result.design,null,2)],{type:"application/json"}),"chameleon-design.json"));
$("download-png").addEventListener("click",()=>save(pngBlob(result.png),"chameleon-design.png"));
$("insert").addEventListener("click",async()=>{
  try { await sdk.app.document.addImage(pngBlob(result.png),{title:"Chameleon adapted design"}); status("Preview added to Express as one image. The JSON keeps the individual elements."); }
  catch(error) { status("Express import failed: "+error.message); }
});
try {
  const health=await request("health"); samples=await request("samples");
  for (const [key,task] of Object.entries(samples)) { const option=document.createElement("option"); option.value=key; option.textContent=task.difficulty_label || key; $("sample").append(option); }
  status("Local engine ready · " + health.renderer + " rendering");
} catch(error) { status("Start the local engine service to continue. " + error.message); }
if (window.parent !== window) {
  try { sdk=(await import("https://express.adobe.com/static/add-on-sdk/sdk.js")).default; await sdk.ready; $("insert").hidden=false; }
  catch(error) { status("Express connection unavailable; local preview and downloads still work."); }
}
