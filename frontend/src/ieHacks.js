// add promises (e.g. I promise you won't need to support anything worse than IE11)
import es6_promise from 'es6-promise';
es6_promise.polyfill();

// graft on support for window.fetch() aka. FUTURE AJAX
import 'fetch-ie8';

// custom events; vue relies on them, IE insistes they're far too spicy
import 'mdn-polyfills/CustomEvent';

// attach array prototype methods that are missing
import 'mdn-polyfills/Array.prototype.find';
import 'mdn-polyfills/NodeList.prototype.forEach';
