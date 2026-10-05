fetch('http://localhost:8000/debates').then(res => res.json()).then(data => console.log(JSON.stringify(data[0].events, null, 2))).catch(console.error)
