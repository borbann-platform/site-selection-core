import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useId, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";

export const Route = createFileRoute("/_public/login")({
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formId = useId();
  const emailId = `${formId}-email`;
  const passwordId = `${formId}-password`;

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login(formData.email, formData.password);
      navigate({ to: "/", search: { district: undefined } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
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
            Welcome Back
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Sign in to your account
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-md text-red-400 text-sm animate-fade-in">
                {error}
              </div>
            )}

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
                className="bg-input border-border text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/40 transition-all duration-200"
                placeholder="Enter your password"
              />
            </div>

            <Button
              type="submit"
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white active:scale-[0.98] transition-all duration-150"
              disabled={isLoading}
            >
              {isLoading ? "Signing in..." : "Sign In"}
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              Don't have an account?{" "}
              <Link to="/register" className="text-emerald-400 hover:text-emerald-300 hover:underline transition-colors">
                Sign up
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
