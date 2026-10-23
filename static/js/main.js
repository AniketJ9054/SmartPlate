document.addEventListener('DOMContentLoaded', function () {
  // Footer copyright year
  const yearNode = document.getElementById('current-year');
  if (yearNode) {
    yearNode.textContent = new Date().getFullYear();
  }

  // Sidebar link active state on click
  const sidebarLinks = document.querySelectorAll('.sidebar-link');
  sidebarLinks.forEach(link => {
    link.addEventListener('click', function () {
      sidebarLinks.forEach(l => l.classList.remove('active'));
      this.classList.add('active');
    });
  });

  // Auto-dismiss success flash messages after 5 seconds
  const flashSuccess = document.querySelectorAll('.flash-success');
  flashSuccess.forEach(flash => {
    setTimeout(() => {
      flash.style.transition = 'opacity 0.4s ease';
      flash.style.opacity = '0';
      setTimeout(() => flash.remove(), 400);
    }, 5000);
  });
});

