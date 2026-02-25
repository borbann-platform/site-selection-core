import { useState } from 'react';
import { User, Bot, Shield, Eye, EyeOff, Trash2 } from 'lucide-react';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Select } from '../components/Select';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';

export function Settings() {
  const [activeTab, setActiveTab] = useState<'profile' | 'ai' | 'security'>('profile');
  const [showApiKey, setShowApiKey] = useState(false);
  
  const [profileData, setProfileData] = useState({
    name: 'John Doe',
    email: 'john@example.com',
    avatar: '',
  });
  
  const [aiConfig, setAiConfig] = useState({
    provider: 'openai',
    apiKey: 'sk-proj-••••••••••••••••••',
    model: 'gpt-4',
    temperature: 0.7,
  });
  
  const tabs = [
    { id: 'profile' as const, label: 'Profile', icon: User },
    { id: 'ai' as const, label: 'AI Model Config', icon: Bot },
    { id: 'security' as const, label: 'Security', icon: Shield },
  ];
  
  const providerOptions = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'anthropic', label: 'Anthropic (Claude)' },
    { value: 'google', label: 'Google (Gemini)' },
    { value: 'azure', label: 'Azure OpenAI' },
  ];
  
  const modelOptions = {
    openai: [
      { value: 'gpt-4', label: 'GPT-4' },
      { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
      { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
    ],
    anthropic: [
      { value: 'claude-3-opus', label: 'Claude 3 Opus' },
      { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
      { value: 'claude-3-haiku', label: 'Claude 3 Haiku' },
    ],
    google: [
      { value: 'gemini-pro', label: 'Gemini Pro' },
      { value: 'gemini-ultra', label: 'Gemini Ultra' },
    ],
    azure: [
      { value: 'gpt-4', label: 'GPT-4' },
      { value: 'gpt-35-turbo', label: 'GPT-3.5 Turbo' },
    ],
  };
  
  const currentModels = modelOptions[aiConfig.provider as keyof typeof modelOptions] || modelOptions.openai;
  
  const handleSaveProfile = () => {
    alert('Profile saved successfully!');
  };
  
  const handleSaveAIConfig = () => {
    alert('AI configuration saved successfully!');
  };
  
  const handleDeleteConfig = () => {
    if (confirm('Are you sure you want to delete your AI configuration?')) {
      setAiConfig({
        provider: 'openai',
        apiKey: '',
        model: 'gpt-4',
        temperature: 0.7,
      });
      alert('AI configuration deleted');
    }
  };
  
  return (
    <div className="min-h-screen pb-20 md:pb-8">
      <div className="max-w-6xl mx-auto p-4 md:p-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Settings</h1>
          <p className="text-muted-foreground">
            Manage your account and application preferences
          </p>
        </div>
        
        <div className="grid lg:grid-cols-[250px_1fr] gap-6">
          {/* Sidebar Navigation */}
          <div className="glass rounded-xl p-2 h-fit hidden lg:block">
            <nav className="space-y-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                      activeTab === tab.id
                        ? 'bg-accent text-accent-foreground'
                        : 'hover:bg-accent/50 text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    <span className="font-medium">{tab.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>
          
          {/* Mobile Tab Buttons */}
          <div className="lg:hidden flex gap-2 overflow-x-auto pb-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg whitespace-nowrap transition-all ${
                    activeTab === tab.id
                      ? 'bg-primary text-primary-foreground'
                      : 'glass text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span className="text-sm font-medium">{tab.label}</span>
                </button>
              );
            })}
          </div>
          
          {/* Content Area */}
          <div>
            {/* Profile Section */}
            {activeTab === 'profile' && (
              <Card>
                <h2 className="text-xl font-semibold mb-6">Profile Information</h2>
                
                <div className="space-y-6">
                  {/* Avatar */}
                  <div className="flex items-center gap-4">
                    <div className="h-20 w-20 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center">
                      <span className="text-2xl font-bold text-white">JD</span>
                    </div>
                    <div>
                      <Button variant="secondary" size="sm">Change Avatar</Button>
                      <p className="text-xs text-muted-foreground mt-1">
                        JPG, PNG or GIF. Max 2MB
                      </p>
                    </div>
                  </div>
                  
                  {/* Form */}
                  <div className="space-y-4">
                    <Input
                      label="Full Name"
                      value={profileData.name}
                      onChange={(e) => setProfileData({ ...profileData, name: e.target.value })}
                    />
                    
                    <Input
                      type="email"
                      label="Email Address"
                      value={profileData.email}
                      onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
                    />
                    
                    <Button onClick={handleSaveProfile}>
                      Save Changes
                    </Button>
                  </div>
                </div>
              </Card>
            )}
            
            {/* AI Config Section */}
            {activeTab === 'ai' && (
              <Card>
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-semibold mb-1">AI Model Configuration</h2>
                    <p className="text-sm text-muted-foreground">
                      Configure your AI provider and model settings (BYOK - Bring Your Own Key)
                    </p>
                  </div>
                  <Badge variant={aiConfig.apiKey ? 'success' : 'danger'}>
                    {aiConfig.apiKey ? 'Configured' : 'Not Configured'}
                  </Badge>
                </div>
                
                <div className="space-y-4">
                  <Select
                    label="AI Provider"
                    options={providerOptions}
                    value={aiConfig.provider}
                    onChange={(e) => setAiConfig({ ...aiConfig, provider: e.target.value })}
                  />
                  
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-foreground">
                      API Key
                    </label>
                    <div className="relative">
                      <input
                        type={showApiKey ? 'text' : 'password'}
                        value={aiConfig.apiKey}
                        onChange={(e) => setAiConfig({ ...aiConfig, apiKey: e.target.value })}
                        placeholder="Enter your API key"
                        className="w-full px-4 py-2.5 pr-12 bg-input-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
                      />
                      <button
                        type="button"
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-accent rounded transition-colors"
                      >
                        {showApiKey ? (
                          <EyeOff className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <Eye className="h-4 w-4 text-muted-foreground" />
                        )}
                      </button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Your API key is encrypted and stored securely
                    </p>
                  </div>
                  
                  <Select
                    label="Model"
                    options={currentModels}
                    value={aiConfig.model}
                    onChange={(e) => setAiConfig({ ...aiConfig, model: e.target.value })}
                  />
                  
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="block text-sm font-medium text-foreground">
                        Temperature
                      </label>
                      <span className="text-sm text-muted-foreground">
                        {aiConfig.temperature}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="2"
                      step="0.1"
                      value={aiConfig.temperature}
                      onChange={(e) => setAiConfig({ ...aiConfig, temperature: parseFloat(e.target.value) })}
                      className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Precise</span>
                      <span>Creative</span>
                    </div>
                  </div>
                  
                  <div className="flex gap-3 pt-4">
                    <Button onClick={handleSaveAIConfig}>
                      Save Configuration
                    </Button>
                    <Button variant="destructive" onClick={handleDeleteConfig}>
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete Config
                    </Button>
                  </div>
                  
                  <div className="mt-6 p-4 glass rounded-lg">
                    <h3 className="font-medium mb-2">Important Notes</h3>
                    <ul className="text-sm text-muted-foreground space-y-1">
                      <li>• Your API key is never shared with third parties</li>
                      <li>• All AI requests are made directly from your browser</li>
                      <li>• You are responsible for your API usage and costs</li>
                      <li>• Site Selection is not meant for collecting PII or securing sensitive data</li>
                    </ul>
                  </div>
                </div>
              </Card>
            )}
            
            {/* Security Section */}
            {activeTab === 'security' && (
              <Card>
                <h2 className="text-xl font-semibold mb-6">Security Settings</h2>
                
                <div className="space-y-6">
                  <div className="space-y-4">
                    <h3 className="font-medium">Change Password</h3>
                    <Input
                      type="password"
                      label="Current Password"
                      placeholder="Enter current password"
                    />
                    <Input
                      type="password"
                      label="New Password"
                      placeholder="Enter new password"
                    />
                    <Input
                      type="password"
                      label="Confirm New Password"
                      placeholder="Confirm new password"
                    />
                    <Button>Update Password</Button>
                  </div>
                  
                  <div className="pt-6 border-t border-border">
                    <h3 className="font-medium mb-3 text-destructive">Danger Zone</h3>
                    <div className="glass-strong rounded-lg p-4 border border-destructive/30">
                      <h4 className="font-medium mb-1">Delete Account</h4>
                      <p className="text-sm text-muted-foreground mb-3">
                        Permanently delete your account and all associated data. This action cannot be undone.
                      </p>
                      <Button variant="destructive">
                        Delete My Account
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
