document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault(); // Prevent form from submitting normally

    const email = document.getElementById("login_email").value;
    const password = document.getElementById("login_password").value;

    try {
        const res = await fetch("/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();

        if (res.ok) {
            // Decide where to redirect
            // If user email exists in your backend check, redirect to /home (user page)
            // Otherwise, redirect to /dashboard (admin page)
            if (data.role === "admin") {
                window.location.href = "/dashboard";
            } else {
                window.location.href = "/home";
            }
        } else {
            document.getElementById("msg").innerText = data.message;
        }
    } catch (err) {
        console.error(err);
        document.getElementById("msg").innerText = "Server error. Try again later.";
    }
});
