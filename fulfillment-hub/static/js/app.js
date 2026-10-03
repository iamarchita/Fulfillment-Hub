document.addEventListener("click", function (e) {
  const wrap = document.querySelector(".bell-wrap");
  const dropdown = document.getElementById("notif-dropdown");
  if (!wrap || !dropdown) return;
  if (!wrap.contains(e.target)) {
    dropdown.classList.remove("open");
  }
});

// Auto-dismiss flash messages after a few seconds.
document.addEventListener("DOMContentLoaded", function () {
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 400);
    }, 6000);
  });
});
