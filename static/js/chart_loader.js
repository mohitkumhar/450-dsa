(function () {
    const sources = [
        "https://cdn.jsdelivr.net/npm/chart.js",
        "https://unpkg.com/chart.js@4/dist/chart.umd.js",
    ];
    let chartJsPromise = null;

    function loadScript(src) {
        return new Promise(function (resolve, reject) {
            const existing = document.querySelector('script[data-chartjs-src="' + src + '"]');
            if (existing) {
                existing.addEventListener(
                    "load",
                    function () {
                        resolve(window.Chart);
                    },
                    { once: true }
                );
                existing.addEventListener(
                    "error",
                    function () {
                        reject(new Error("Failed to load Chart.js from " + src));
                    },
                    { once: true }
                );
                return;
            }

            const script = document.createElement("script");
            script.src = src;
            script.async = true;
            script.dataset.chartjsSrc = src;
            script.addEventListener(
                "load",
                function () {
                    resolve(window.Chart);
                },
                { once: true }
            );
            script.addEventListener(
                "error",
                function () {
                    script.remove();
                    reject(new Error("Failed to load Chart.js from " + src));
                },
                { once: true }
            );
            document.head.appendChild(script);
        });
    }

    window.loadChartJs = function () {
        if (window.Chart) {
            return Promise.resolve(window.Chart);
        }

        if (!chartJsPromise) {
            chartJsPromise = sources
                .reduce(function (promise, src) {
                    return promise.catch(function () {
                        return loadScript(src).then(function (ChartCtor) {
                            if (!ChartCtor) {
                                throw new Error("Chart.js loaded without constructor");
                            }
                            return ChartCtor;
                        });
                    });
                }, Promise.reject(new Error("Chart.js not loaded yet")))
                .catch(function (error) {
                    chartJsPromise = null;
                    throw error;
                });
        }

        return chartJsPromise;
    };
})();
