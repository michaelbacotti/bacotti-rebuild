(function() {
 var nav = document.getElementById('site-nav');
 if (nav) {
 nav.innerHTML = [
 '<div class="container">',
 '<a href="/" class="nav-logo">Bacotti Inc.</a>',
 '<nav class="main-nav">',
 '<ul>',
 '<li><a href="/">Home</a></li>',
 '<li><a href="/entities.html">Entities &amp; Governance</a></li>',
 '<li><a href="/services.html">Services</a></li>',
 '<li><a href="/legacy.html">Legacy</a></li>',
 '<li><a href="/contact.html">Contact</a></li>',
 '</ul>',
 '</nav>',
 '</div>'
 ].join('\n');
 }
})();