# PawPal+ enhanced reflection

-There is the limitation in the way that care is suggested to the user, it uses strictly text from the knowledge_base file, which makes all recommendations be based only on the information retrieved from that file and not any other source. This can lead to outdated information, or information that might have been from only one source with little verification for accuracy. 

-AI can definitely be misused to give erronous care instructions to a pet. If the model picked up information stored in the knowledge_base file that came from a source with incorrect information, this can lead to incorrect recommendations on case. A way to prevent this would be to source control the knowledge base into trusted sources and human review the information for accuracy.


-The most surprising bug was that the scheduled tasks table appeared empty after generating a schedule. The cause wasn't obvious — sort_by_time was filtering to only tasks with a time field set, and since tasks created through the UI all have time=None by default, the entire list was silently discarded after sorting. The scheduler ran fine, the plan generated correctly, but by the time it reached the display it was empty. Nothing crashed, no error was raised — it just quietly dropped every task. That kind of silent failure is harder to catch than an exception.


-AI collaboration helped greatly to enhance this project, it really leveraged RAG to make good suggestions in pet care from a retrieved knowdledge base. However, some of the flawed suggestions were on the use of paid AI models that would lead me to spend tokens for each suggestion, where there are many open source LLMs that do not incur charges from low, personal usage. From a programming perspective, some suggestions led to silent erros (empty schedule) and a repeated section of plan explanation. 

