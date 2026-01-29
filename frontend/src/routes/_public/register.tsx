import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useId, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";

export const Route = createFileRoute("/_public/register")({
  component: RegisterPage,
});

function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formId = useId();
  const firstNameId = `${formId}-first-name`;
  const lastNameId = `${formId}-last-name`;
  const emailId = `${formId}-email`;
  const passwordId = `${formId}-password`;
  const confirmPasswordId = `${formId}-confirm-password`;

  const [formData, setFormData] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    firstName: "",
    lastName: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation guards
    if (formData.password !== formData.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (formData.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    // Password strength check (uppercase, lowercase, number)
    const hasUppercase = /[A-Z]/.test(formData.password);
    const hasLowercase = /[a-z]/.test(formData.password);
    const hasNumber = /[0-9]/.test(formData.password);

    if (!hasUppercase || !hasLowercase || !hasNumber) {
      setError("Password must contain uppercase, lowercase, and a number");
      return;
    }

    setIsLoading(true);

    try {
      await register(
        formData.email,
        formData.password,
        formData.confirmPassword,
        formData.firstName,
        formData.lastName
      );
      navigate({ to: "/", search: { district: undefined } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-emerald-950/20 flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-card border-border shadow-2xl shadow-black/10 animate-fade-in">
        <CardHeader className="text-center">
          <div className="w-12 h-12 bg-emerald-500 rounded-xl flex items-center justify-center font-bold text-black text-xl mx-auto mb-4 shadow-lg shadow-emerald-500/25">
            K
          </div>
          <CardTitle className="text-2xl font-bold text-foreground">
            Create Account
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Sign up to access the Real Estate Platform
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-md text-red-400 text-sm animate-fade-in">
                {error}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                  <Label htmlFor={firstNameId} className="text-foreground">
                    First Name
                  </Label>
                  <Input
                    id={firstNameId}
                    name="firstName"
                    type="text"
                    value={formData.firstName}
                  onChange={handleChange}
                  required
                  className="bg-input border-border text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/40 transition-all duration-200"
                  placeholder="John"
                />
              </div>
              <div className="space-y-2">
                  <Label htmlFor={lastNameId} className="text-foreground">
                    Last Name
                  </Label>
                  <Input
                    id={lastNameId}
                    name="lastName"
                    type="text"
                    value={formData.lastName}
                  onChange={handleChange}
                  required
                  className="bg-input border-border text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/40 transition-all duration-200"
                  placeholder="Doe"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor={emailId} className="text-foreground">
                Email
              </Label>
              <Input
                id={emailId}
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                required
                className="bg-input border-border text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/40 transition-all duration-200"
                placeholder="john@example.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor={passwordId} className="text-foreground">
                Password
              </Label>
              <Input
                id={passwordId}
                name="password"
                type="password"
                value={formData.password}
                onChange={handleChange}
                required
                minLength={8}
                className="bg-input border-border text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/40 transition-all duration-200"
                placeholder="Min 8 characters"
              />
              <p className="text-xs text-muted-foreground">
                Must contain uppercase, lowercase, and a number
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor={confirmPasswordId} className="text-foreground">
                Confirm Password
              </Label>
              <Input
                id={confirmPasswordId}
                name="confirmPassword"
                type="password"
                value={formData.confirmPassword}
                onChange={handleChange}
                required
                className="bg-input border-border text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/40 transition-all duration-200"
                placeholder="Repeat your password"
              />
            </div>

            <Button
              type="submit"
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white active:scale-[0.98] transition-all duration-150"
              disabled={isLoading}
            >
              {isLoading ? "Creating account..." : "Create Account"}
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link to="/login" className="text-emerald-400 hover:text-emerald-300 hover:underline transition-colors">
                Sign in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
