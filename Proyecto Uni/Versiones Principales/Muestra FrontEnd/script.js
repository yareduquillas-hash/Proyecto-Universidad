document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    
    if (loginForm) {
        loginForm.addEventListener('submit', (evento) => {
            evento.preventDefault(); 
            
            const rolSeleccionado = document.getElementById('rol').value;
            
            if (rolSeleccionado === 'profesor') {
                // Si es profesor, ve al ejemplo
                window.location.href = 'example.html';
            } else {
                // Si es estudiante, Error
                alert('¡Hola Integrante! El acceso para estudiantes estará disponible próximamente en este prototipo.');
            }
        });
    }
});