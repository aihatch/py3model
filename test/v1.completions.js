const config = require("./config.js")

const params = {
    model: config.model,
    prompt: "用一句话介绍你自己。",
    stream: true
}

let data = ""
const body = JSON.stringify(params)
const req = require(config.request).request({
    hostname: config.hostname,
    port: config.port,
    path: config.path + '/completions', // 文本补全接口
    method: 'POST',
    headers: {
        Authorization: 'Bearer ' + config.apiKey,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
    }
}, (res) => {
    res.on('data', (chunk) => {
        if (params.stream) {
            chunk.toString().replace(/data: (.+)/g, (match, p1) => {
                if (p1 === "[DONE]") {
                    console.log("[结束]")
                } else {
                    let json = JSON.parse(p1)
                    process.stdout.write(json.choices[0].text || "")
                }
            })
        } else {
            data += chunk
        }
    })
    res.on('end', () => {
        if (!params.stream) console.log("[完整数据]", data)
        console.log("[结束]")
    })
})

req.write(body)
req.on('error', (e) => {
    console.log("[发生错误]", e)
})

req.end()
