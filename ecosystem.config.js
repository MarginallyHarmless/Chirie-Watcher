module.exports = {
  apps: [
    {
      name: "imobiliare-dashboard",
      script: "python3",
      args: "server.py",
      cwd: __dirname,
      autorestart: true,
      max_restarts: 10,
    },
    {
      name: "imobiliare-scraper",
      script: "python3",
      args: "scraper.py",
      cwd: __dirname,
      cron_restart: "0 8-23 * * *",
      autorestart: false,
    },
  ],
};
