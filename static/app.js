function previewImage(event) {
  const img = document.getElementById("previewImg");
  const icon = document.getElementById("previewIcon");
  const text = document.getElementById("previewText");

  const file = event.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = function (e) {
      img.src = e.target.result;
      img.style.display = "block";
      icon.style.display = "none";
      text.textContent = "Imagen seleccionada ✅";
    };
    reader.readAsDataURL(file);
  }
}
