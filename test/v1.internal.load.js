const config = require("./config.js")

if (!config.modelPath) {
    console.log("[配置错误] 请先在 test/config.js 中设置 modelPath 为本地 .gguf 文件绝对路径")
    process.exit(1)
}

const params = {
    model_path: config.modelPath,
    n_ctx: 8192,
    n_threads: null,
    n_gpu_layers: -1
}

const body = JSON.stringify(params)
const req = require(config.request).request({
    hostname: config.hostname,
    port: config.port,
    path: config.path + '/internal/load', // 内部加载模型接口
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
