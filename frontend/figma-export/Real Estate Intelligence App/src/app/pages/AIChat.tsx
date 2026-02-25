import { useState } from 'react';
import { Send, Plus, Search, Bot, User, ChevronDown, MapPin, Sparkles } from 'lucide-react';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';
import { motion, AnimatePresence } from 'motion/react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: { step: string; result: string }[];
  timestamp: Date;
}

interface Session {
  id: string;
  title: string;
  preview: string;
  date: string;
  messages: Message[];
}

const mockSessions: Session[] = [
  {
    id: '1',
    title: 'Properties near BTS',
    preview: 'Looking for condos within 500m of BTS stations',
    date: '2026-02-19',
    messages: [
      {
        id: 'm1',
        role: 'user',
        content: 'Show me condos within 500m of BTS stations in Sukhumvit',
        timestamp: new Date('2026-02-19T10:00:00'),
      },
      {
        id: 'm2',
        role: 'assistant',
        content: 'I found 23 condos within 500m of BTS stations in the Sukhumvit area. The average price is ฿85M with prices ranging from ฿45M to ฿150M. Most properties are 5-10 years old with modern amenities. Would you like me to show specific properties or filter by price range?',
        thinking: [
          { step: 'Query database', result: 'Found 23 properties matching criteria' },
          { step: 'Calculate statistics', result: 'Avg: ฿85M, Range: ฿45M-150M' },
          { step: 'Analyze features', result: '5-10 years old, modern amenities' },
        ],
        timestamp: new Date('2026-02-19T10:00:05'),
      },
    ],
  },
  {
    id: '2',
    title: 'Price prediction analysis',
    preview: 'What factors affect property prices in Thonglor?',
    date: '2026-02-18',
    messages: [],
  },
  {
    id: '3',
    title: 'Investment opportunities',
    preview: 'Best areas for long-term investment',
    date: '2026-02-17',
    messages: [],
  },
];

export function AIChat() {
  const [sessions, setSessions] = useState(mockSessions);
  const [activeSessionId, setActiveSessionId] = useState('1');
  const [searchQuery, setSearchQuery] = useState('');
  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [showThinking, setShowThinking] = useState<string | null>(null);
  
  const activeSession = sessions.find(s => s.id === activeSessionId);
  const messages = activeSession?.messages || [];
  
  const handleSendMessage = () => {
    if (!inputValue.trim()) return;
    
    const newMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    };
    
    setSessions(prev => prev.map(session => 
      session.id === activeSessionId
        ? { ...session, messages: [...session.messages, newMessage] }
        : session
    ));
    
    setInputValue('');
    setIsThinking(true);
    
    // Simulate AI response
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Based on your query, I\'ve analyzed the Bangkok property market data. Here are my insights: The properties you\'re interested in show strong investment potential with an average annual appreciation of 8-12%. Location factors like proximity to BTS stations significantly influence prices, adding approximately 15-20% premium.',
        thinking: [
          { step: 'Analyzing market data', result: 'Processing 15,000+ properties' },
          { step: 'Calculating appreciation rates', result: '8-12% annual growth' },
          { step: 'Evaluating location factors', result: 'BTS proximity adds 15-20% premium' },
        ],
        timestamp: new Date(),
      };
      
      setSessions(prev => prev.map(session => 
        session.id === activeSessionId
          ? { ...session, messages: [...session.messages, aiMessage] }
          : session
      ));
      
      setIsThinking(false);
    }, 2000);
  };
  
  const createNewSession = () => {
    const newSession: Session = {
      id: Date.now().toString(),
      title: 'New Chat',
      preview: 'Start a new conversation',
      date: new Date().toISOString().split('T')[0],
      messages: [],
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
  };
  
  return (
    <div className="h-[calc(100vh-4rem)] flex overflow-hidden">
      {/* Left Sidebar - Sessions */}
      <div className="w-80 border-r border-border flex flex-col glass hidden md:flex">
        <div className="p-4 border-b border-border space-y-3">
          <Button onClick={createNewSession} className="w-full" variant="primary">
            <Plus className="h-4 w-4 mr-2" />
            New Chat
          </Button>
          
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search sessions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-input-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => setActiveSessionId(session.id)}
              className={`w-full text-left p-3 rounded-lg transition-all ${
                activeSessionId === session.id
                  ? 'bg-accent text-accent-foreground'
                  : 'hover:bg-accent/50'
              }`}
            >
              <div className="font-medium text-sm truncate">{session.title}</div>
              <div className="text-xs text-muted-foreground truncate mt-1">{session.preview}</div>
              <div className="text-xs text-muted-foreground mt-1">{session.date}</div>
            </button>
          ))}
        </div>
      </div>
      
      {/* Right Chat Area */}
      <div className="flex-1 flex flex-col bg-background/50">
        {/* Chat Header */}
        <div className="p-4 border-b border-border glass-strong flex items-center justify-between">
          <div>
            <h2 className="font-semibold">{activeSession?.title}</h2>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="success">AI Configured</Badge>
              <span className="text-xs text-muted-foreground">GPT-4 • BYOK</span>
            </div>
          </div>
        </div>
        
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center px-4">
              <div className="h-20 w-20 rounded-full bg-primary/20 flex items-center justify-center mb-4">
                <Sparkles className="h-10 w-10 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Start a Conversation</h3>
              <p className="text-muted-foreground max-w-md">
                Ask me anything about Bangkok real estate, property valuations, market trends, or location analysis.
              </p>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.role === 'assistant' && (
                    <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                      <Bot className="h-6 w-6 text-primary-foreground" />
                    </div>
                  )}
                  
                  <div className={`max-w-2xl ${message.role === 'user' ? 'order-first' : ''}`}>
                    {message.role === 'assistant' && message.thinking && (
                      <div className="mb-3">
                        <button
                          onClick={() => setShowThinking(showThinking === message.id ? null : message.id)}
                          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <Sparkles className="h-4 w-4" />
                          Thinking steps
                          <ChevronDown className={`h-4 w-4 transition-transform ${showThinking === message.id ? 'rotate-180' : ''}`} />
                        </button>
                        
                        <AnimatePresence>
                          {showThinking === message.id && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              className="mt-2 glass rounded-lg p-3 space-y-2"
                            >
                              {message.thinking.map((step, i) => (
                                <div key={i} className="text-sm">
                                  <div className="font-medium text-primary">{step.step}</div>
                                  <div className="text-muted-foreground">{step.result}</div>
                                </div>
                              ))}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}
                    
                    <div className={`p-4 rounded-2xl ${
                      message.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'glass'
                    }`}>
                      {message.content}
                    </div>
                    
                    <div className="text-xs text-muted-foreground mt-1 px-1">
                      {message.timestamp.toLocaleTimeString()}
                    </div>
                  </div>
                  
                  {message.role === 'user' && (
                    <div className="h-10 w-10 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center flex-shrink-0">
                      <User className="h-6 w-6 text-white" />
                    </div>
                  )}
                </div>
              ))}
              
              {isThinking && (
                <div className="flex gap-4 justify-start">
                  <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                    <Bot className="h-6 w-6 text-primary-foreground" />
                  </div>
                  <div className="glass p-4 rounded-2xl">
                    <div className="flex gap-1">
                      <motion.div
                        className="h-2 w-2 rounded-full bg-primary"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 1, repeat: Infinity, delay: 0 }}
                      />
                      <motion.div
                        className="h-2 w-2 rounded-full bg-primary"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 1, repeat: Infinity, delay: 0.2 }}
                      />
                      <motion.div
                        className="h-2 w-2 rounded-full bg-primary"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 1, repeat: Infinity, delay: 0.4 }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        
        {/* Input Area */}
        <div className="p-4 border-t border-border glass-strong">
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-2 mb-2">
              <Badge variant="neutral" className="cursor-pointer">
                <MapPin className="h-3 w-3 mr-1" />
                Sukhumvit Area
              </Badge>
            </div>
            
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Ask about properties, prices, locations..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                className="flex-1 px-4 py-3 bg-input-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <Button onClick={handleSendMessage} className="px-6">
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
