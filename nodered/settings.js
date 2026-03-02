module.exports = {
    uiPort: process.env.PORT || 1880,
    mqttReconnectTime: 15000,
    serialReconnectTime: 15000,
    debugMaxLength: 1000,
    flowFile: 'flows.json',
    flowFilePretty: true,
    userDir: '/data',
    nodesDir: '/data/nodes',
    adminAuth: null,        // No auth — dev environment only
    httpNodeAuth: null,
    httpStaticAuth: null,
    tlsConfigDisableLocalFiles: false,
    editorTheme: {
        projects: { enabled: false },
        palette: { catalogues: ['https://catalogue.nodered.org/catalogue.json'] },
        header: {
            title: "ACME Factory Edge Device",
        },
        tours: false,
    },
    logging: {
        console: {
            level: "info",
            metrics: false,
            audit: false,
        }
    },
    exportGlobalContextKeys: false,
    externalModules: {
        autoInstall: true,
        autoInstallRetry: 30,
        palette: { allowInstall: true, allowUpload: true, allowList: [], denyList: [] },
        modules: { allowInstall: true, allowList: [], denyList: [] },
    },
    functionExternalModules: true,
    functionTimeout: 0,
    debugUseColors: true,
    runtimeState: { enabled: false, ui: false },
    diagnostics: { enabled: true, ui: true },
};
