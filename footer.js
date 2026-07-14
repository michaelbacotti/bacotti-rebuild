(function() {
 var footer = document.getElementById('site-footer');
 if (footer) {
 footer.innerHTML = [
 '<div class="container">',
 '<p>&copy; 2026 Bacotti Inc. All rights reserved.</p>',
 '<p>Bacotti Inc. is a private family office. tredey.com is operated by Bacotti Inc. This website contains general information only.</p>',
 '</div>'
 ].join('\n');
 }
})();