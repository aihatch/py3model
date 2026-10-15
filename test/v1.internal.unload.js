const config = require("./config.js")

const body = JSON.stringify({})
const req = require(config.request).request({
    hostname: config.hostname,
    port: config.port,
    path: config.path + '/internal/unload', // 内部卸载模型接口
    method: 'POST',
    headers: {
        Authorization: 'Bearer ' + config.apiKey,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
    }
}, (res) => {
    let data = ""
    res.on('data', (chunk) => {
        data += chunk
    })
    res.on('end', () => {
        console.log("[状态码]", res.statusCode)
        console.log("[完整数据]", data)
    })
})

req.write(body)
req.on('error', (e) => {
    console.log("[发生错误]", e)
})

req.end()
