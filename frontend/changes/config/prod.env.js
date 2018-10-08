module.exports = {
  NODE_ENV: '"production"',
  PARKSTAY_URL: process.env.PARKSTAY_URL ? JSON.stringify(process.env.PARKSTAY_URL) : '""'
}
