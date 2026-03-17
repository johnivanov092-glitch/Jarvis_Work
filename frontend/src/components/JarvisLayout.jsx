
import { useState, useRef } from "react";
import { Plus, Search, MessageSquare, Folder, Settings, Paperclip, Send } from "lucide-react";

export default function JarvisLayout(){

const [messages,setMessages]=useState([])
const [input,setInput]=useState("")
const [files,setFiles]=useState([])

const fileRef=useRef()

function send(){
 if(!input && files.length===0) return
 setMessages([...messages,{text:input,files}])
 setInput("")
 setFiles([])
}

function addFiles(e){
 const f=[...e.target.files]
 setFiles([...files,...f])
}

return(
<div className="app">

<aside className="sidebar">

<button className="newChat">
<Plus size={16}/> Новый чат
</button>

<div className="nav">
<button><Search size={16}/> Search</button>
<button><MessageSquare size={16}/> Chats</button>
<button><Folder size={16}/> Projects</button>
<button><Settings size={16}/> Settings</button>
</div>

</aside>

<main className="main">

<header className="top">
<div className="title">Jarvis Агент ИИ</div>

<div className="tabs">
<button>Чат</button>
<button>Code</button>
</div>
</header>

<section className="chat">

<div className="messages">
{messages.map((m,i)=>(
<div key={i} className="msg">
<div>{m.text}</div>
{m.files.map((f,j)=>(<div key={j}>{f.name}</div>))}
</div>
))}
</div>

<div className="composer">

<input type="file" multiple ref={fileRef} onChange={addFiles} style={{display:"none"}}/>

<button onClick={()=>fileRef.current.click()} className="attach">
<Paperclip size={16}/>
</button>

<input
value={input}
onChange={e=>setInput(e.target.value)}
placeholder="Напиши задачу…"
/>

<button onClick={send} className="send">
<Send size={16}/>
</button>

</div>

</section>

</main>

</div>
)
}
