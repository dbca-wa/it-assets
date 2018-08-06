//var webpack = require('webpack');

module.exports = {
    pages: {
        addressbook: {
            entry: 'src/addressbook/main.js',
            template: 'public/addressbook.html',
            filename: 'addressbook.html',
        }
    },
    
    css: {
        extract: false,
        sourceMap: false
    },

    baseUrl: ((process.env.NODE_ENV === 'production') ? '/static/' : undefined),
    outputDir: 'static',
    assetsDir: undefined,
    productionSourceMap: undefined,
    parallel: undefined,
    
    configureWebpack: function (config) {
        // expose the init function as a global 
        config.output.library = '[name]App';
        config.output.libraryTarget = 'var';
        config.output.libraryExport = 'default';
        
        // if production, remove the cache-hint hash from file names
        if (process.env.NODE_ENV === 'production') {
            config.output.filename = 'js/[name].js';
            config.output.chunkFilename = 'js/[name].js';
        }

    },

};
