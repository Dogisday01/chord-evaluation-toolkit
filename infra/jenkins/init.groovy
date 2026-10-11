import jenkins.model.Jenkins
import hudson.model.Node
import hudson.model.ParametersDefinitionProperty
import hudson.model.StringParameterDefinition
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.slaves.DumbSlave
import hudson.slaves.RetentionStrategy
import hudson.plugins.sshslaves.SSHLauncher
import hudson.plugins.sshslaves.verifiers.ManuallyProvidedKeyVerificationStrategy
import hudson.plugins.git.GitSCM
import hudson.plugins.git.BranchSpec
import hudson.plugins.git.UserRemoteConfig
import com.cloudbees.plugins.credentials.CredentialsScope
import com.cloudbees.plugins.credentials.SystemCredentialsProvider
import com.cloudbees.plugins.credentials.domains.Domain
import com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition
import jenkins.model.JenkinsLocationConfiguration

def instance = Jenkins.get()
def secret = { name -> new File('/run/secrets/' + name).getText('UTF-8').trim() }
def password = secret('admin_password')
if (password.length() < 24) throw new IllegalStateException('Admin password must have 24 characters')
def realm = new HudsonPrivateSecurityRealm(false)
realm.createAccount('admin', password)
instance.setSecurityRealm(realm)
def authorization = new FullControlOnceLoggedInAuthorizationStrategy()
authorization.setAllowAnonymousRead(false)
instance.setAuthorizationStrategy(authorization)
instance.setNumExecutors(0)
instance.setSlaveAgentPort(-1)
JenkinsLocationConfiguration.get().setUrl('http://localhost:8080/')

def privateKey = new BasicSSHUserPrivateKey(CredentialsScope.SYSTEM, 'chord-agent-ssh',
    'jenkins', new BasicSSHUserPrivateKey.DirectEntryPrivateKeySource(secret('agent_private_key')),
    '', 'Dedicated local SSH agent')
def store = SystemCredentialsProvider.getInstance().getStore()
def existing = store.getCredentials(Domain.global()).find { it.id == 'chord-agent-ssh' }
if (existing) store.updateCredentials(Domain.global(), existing, privateKey)
else store.addCredentials(Domain.global(), privateKey)
def hostKey = secret('agent_host_public_key').split(' ').take(2).join(' ')
def launcher = new SSHLauncher('agent', 22, 'chord-agent-ssh', '-Xmx512m',
    '/opt/java/openjdk/bin/java', '', '', 60, 10, 15,
    new ManuallyProvidedKeyVerificationStrategy(hostKey))
def node = new DumbSlave('docker-agent', 'Dedicated trusted build agent', '/home/jenkins',
    '2', Node.Mode.EXCLUSIVE, 'docker', launcher, new RetentionStrategy.Always(), [])
instance.addNode(node)

def repository = System.getenv('TRUSTED_REPO_URL')
def branch = System.getenv('TRUSTED_BRANCH')
if (!(repository ==~ /https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\.git/)) {
    throw new IllegalStateException('Expected trusted public GitHub HTTPS repository')
}
if (!(branch ==~ /[A-Za-z0-9][A-Za-z0-9_.\/-]*/) || branch.contains('..')) {
    throw new IllegalStateException('Invalid trusted branch')
}
def configureJob = { name, scriptPath ->
    def job = instance.getItem(name) ?: instance.createProject(WorkflowJob, name)
    def scm = new GitSCM([new UserRemoteConfig(repository, null, null, null)],
        [new BranchSpec('*/' + branch)], false, [], null, null, [])
    def definition = new CpsScmFlowDefinition(scm, scriptPath)
    definition.setLightweight(true)
    job.setDefinition(definition)
    job.save()
    return job
}
def worker = configureJob('chord-evaluation-worker', 'Jenkinsfile')
worker.removeProperty(ParametersDefinitionProperty)
worker.addProperty(new ParametersDefinitionProperty([
    new StringParameterDefinition('COMMIT_SHA', '', 'Optional exact trusted 40-character SHA'),
    new StringParameterDefinition('TRACKED_BRANCH', branch, 'Trusted branch containing revision')
]))
configureJob('chord-evaluation-dispatcher', 'infra/jenkins/dispatcher.Jenkinsfile')
instance.save()
println('Provisioned authenticated controller, verified SSH agent, and two SCM pipelines')
