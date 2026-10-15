const config = require("./config.js")

const rootPath = (config.path || "").replace(/\/v1\/?$/, "")

const req = require(config.request).request({
    hostname: config.hostname,
    port: config.port,
    path: rootPath + '/health', // 健康检查接口
    method: 'GET',
    headers: {
        Authorization: 'Bearer ' + config.apiKey
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

req.on('error', (e) => {
    console.log("[发生错误]", e)
})

req.end()
