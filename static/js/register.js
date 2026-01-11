document.getElementById("registerForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = {
        owner_name: document.getElementById("owner_name").value,
        email: document.getElementById("reg_email").value,
        phone: document.getElementById("phone").value,
        password: document.getElementById("reg_password").value
    };
    const res = await fetch("/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });
    const result = await res.json();
    alert(result.message);

    
});
