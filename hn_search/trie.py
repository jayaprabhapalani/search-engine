class TrieNode():

    
    def __init__(self):
        self.children={}
        self.is_end=False


class Trie():
    
    def __init__(self):
        self.root=TrieNode()
        
    def insert(self,word):
        cur=self.root
        
        for char in word:
            if char not in cur.children:
               cur.children[char]=TrieNode() # create a new word
            cur=cur.children[char] # always move forward
        
        cur.is_end=True    
        
    
    def _collect_words(self,node,prefix):
        results=[]
        
        if node.is_end is True:
            results.append(prefix)
        
        for char,k in node.children.items():
            results.extend(self._collect_words(k,prefix+char))
            
        return results   
    
    def search(self,prefix,limit=10):
        cur=self.root
        
        for char in prefix:
            if char not in cur.children:
                return []  # prefix doesn't exists
            
            cur=cur.children[char]
            
        #now -at the end of the prefix node
        # collect all wrs from here
        results=self._collect_words(cur,prefix)
        
        return results[:limit]           
                 
    