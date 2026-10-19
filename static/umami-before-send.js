// Fun with Quantum family standard Umami filter (same on every family site).
// ?notrack switches tracking off for this browser, ?track switches it back on;
// the tracker calls fwqUmamiBeforeSend (data-before-send) and drops anything
// sent by a headless browser or a bot.
(function(){try{var q=location.search;if(/[?&]notrack\b/.test(q))localStorage.setItem('umami.disabled','1');if(/[?&]track\b/.test(q))localStorage.removeItem('umami.disabled')}catch(e){}window.fwqUmamiBeforeSend=function(t,p){var n=navigator;return(n.webdriver||/HeadlessChrome|bot|crawl|spider|Lighthouse|PageSpeed/i.test(n.userAgent))?false:p}})();
